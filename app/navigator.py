from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Optional

import orjson

from .audit import AuditTrailAgent
from .browser import open_page, open_persistent, export_storage_state, goto_with_retry, set_fixture_html, dump_html, screenshot
from .detectors import detect_platform, url_guess, probe_platform, find_external_apply_links, is_ats_url
from .urltools import canonicalize, host as url_host, prefer_meta_canonical
from .auth import SessionManager, AuthGateDetector
from .extractors import extract_fields, description_roots_for
from .expanders import expand_description, scroll_lazy
from .normalize import normalize_fields
from .schemas import JobRecord
from .settings import settings
from .hashing import sha256_file, sha256_bytes
from . import storage


class NavigatorAgent:
    def __init__(self) -> None:
        self.audit = AuditTrailAgent()
        self._last_run_id = None
        self._llm_enabled_override = True

    def log_event(self, *args, **kwargs):
        return self.audit.log_event(*args, **kwargs)

    def run(self, url: str, fixture_path: Optional[str] = None, headless: Optional[bool] = None) -> JobRecord:
        # Canonicalize URL
        canon = canonicalize(url)
        run_id = storage.create_run(canon)
        run_dir = settings.artifacts_dir_for(run_id)

        self.log_event(
            run_id,
            step="run_started",
            status="ok",
            details={"url": url, "cfg_hash": settings.cfg_hash},
        )

        pw = browser = context = page = None
        try:
            sess = SessionManager()
            auth = AuthGateDetector()
            h = url_host(canon)
            state = sess.load_state(h)
            self.log_event(run_id, step="auth.session_loaded", status="ok", details={"host": h, "path": str(sess.state_path_for(h)), "exists": bool(state)})

            if url != canon:
                self.log_event(run_id, step="url.canonicalized", status="ok", details={"from": url, "to": canon})

            # Open browser with persistent state
            pw, browser, context, page = open_persistent(headless=(headless if headless is not None else bool(settings.playwright.get("headless", True))), storage_state=state)

            if fixture_path:
                html = Path(fixture_path).read_text(encoding="utf-8")
                set_fixture_html(page, html)
                self.log_event(
                    run_id,
                    step="navigate.fetch_html",
                    status="ok",
                    details={"mode": "fixture", "bytes": len(html)},
                    output_digest=sha256_bytes(html.encode("utf-8")),
                    artifact_paths=[],
                )
            else:
                goto_with_retry(page, canon, timeout_ms=int(settings.playwright.get("nav_timeout_ms", 15000)))
                html = page.content()
                self.log_event(
                    run_id,
                    step="navigate.fetch_html",
                    status="ok",
                    details={"mode": "live", "bytes": len(html)},
                    output_digest=sha256_bytes(html.encode("utf-8")),
                    artifact_paths=[],
                )
                # Meta canonical
                meta = prefer_meta_canonical(page)
                if meta and strip_tracking(meta) != strip_tracking(canon):
                    self.log_event(run_id, step="url.canonicalized_meta", status="ok", details={"from": canon, "to": meta})
                    goto_with_retry(page, meta, timeout_ms=int(settings.playwright.get("nav_timeout_ms", 15000)))

            # Detect auth gate always; manual flow only in live mode
            gate = auth.is_login_gate(page, h)
            if gate:
                self.log_event(run_id, step="auth.required", status="ok", details={"host": h, "reason": "login_gate_detected"})
                if not settings.auth.get("allow_manual_login", True):
                    storage.finish_run(run_id, status="auth_required", error_message="Manual login disabled")
                    raise RuntimeError("auth_required: manual login disabled")
                if not fixture_path:
                    # Switch to headful if currently headless
                    if (headless if headless is not None else bool(settings.playwright.get("headless", True))):
                        try:
                            page.close(); context.close(); browser.close(); pw.stop()
                        except Exception:
                            pass
                        pw, browser, context, page = open_persistent(headless=False, storage_state=state)
                        goto_with_retry(page, canon, timeout_ms=int(settings.playwright.get("nav_timeout_ms", 15000)))

                    # Instruction to user via stdout
                    timeout_s = int(settings.auth.get("manual_login_timeout_s", 420))
                    print(f"Manual login required for {h}. Complete login in the opened window, then press Enter to continue (timeout {timeout_s}s).", flush=True)
                    try:
                        import select, sys
                        rlist, _, _ = select.select([sys.stdin], [], [], timeout_s)
                        if rlist:
                            sys.stdin.readline()
                    except Exception:
                        pass
                    # Wait until logged in marker appears or timeout
                    import time as _t
                    deadline = _t.time() + timeout_s
                    logged = False
                    while _t.time() < deadline:
                        if auth.is_logged_in(page, h):
                            self.log_event(run_id, step="auth.logged_in_marker", status="ok", details={"host": h})
                            logged = True
                            break
                        _t.sleep(1)
                    if logged:
                        # Save storage state
                        state = export_storage_state(context)
                        path = SessionManager().save_state(h, state)
                        self.log_event(run_id, step="auth.session_saved", status="ok", details={"host": h, "path": str(path)})
                        goto_with_retry(page, canon, timeout_ms=int(settings.playwright.get("nav_timeout_ms", 15000)))

            # Save raw BEFORE HTML (configurable)
            if settings.artifacts.get("keep_raw_before_after", True):
                raw_before = run_dir / "raw.before.html"
                dump_html(page, raw_before)
                storage.persist_artifact(run_id, kind="raw_html_before", path=raw_before)

            # Detect platform (log both URL guess and DOM probe) early so we know which expander to use
            guess = url_guess(canon)
            self.log_event(
                run_id,
                step="detect_platform.url_pattern",
                status="ok",
                details={"platform_guess": guess.name, "matched": guess.name != "other"},
            )
            probe = probe_platform(page)
            self.log_event(
                run_id,
                step="detect_platform.dom_probe",
                status="ok",
                details={"platform": probe.name, "selector_hits": probe.matched_selectors, "confidence": probe.confidence},
            )
            plat = probe if probe.name != "other" else guess

            # Expand collapsed descriptions before extraction
            desc_roots = description_roots_for(plat.name)
            exp = expand_description(page, plat.name, desc_roots, settings)
            self.log_event(
                run_id,
                step="expand.see_more",
                status="ok",
                details={
                    "attempts": exp.get("attempts", 0),
                    "selectors_tried": exp.get("selectors_tried", []),
                    "before_len": exp.get("before_len", 0),
                    "after_len": exp.get("after_len", 0),
                    "expanded": exp.get("expanded", False),
                },
            )
            if not exp.get("expanded", False):
                scroll_lazy(page)
                self.log_event(run_id, step="dom.scroll_lazy", status="ok", details={"scrolls": 4})
                exp2 = expand_description(page, plat.name, desc_roots, settings)
                self.log_event(
                    run_id,
                    step="expand.see_more",
                    status="ok",
                    details={
                        "attempts": exp2.get("attempts", 0),
                        "selectors_tried": exp2.get("selectors_tried", []),
                        "before_len": exp2.get("before_len", 0),
                        "after_len": exp2.get("after_len", 0),
                        "expanded": exp2.get("expanded", False),
                    },
                )

            # Save raw AFTER HTML
            if settings.artifacts.get("keep_raw_before_after", True):
                raw_after = run_dir / "raw.after.html"
                dump_html(page, raw_after)
                storage.persist_artifact(run_id, kind="raw_html_after", path=raw_after)

            # Screenshot
            ss_disabled = getattr(self, "_screenshot_enabled", True)
            if ss_disabled:
                ss_path = run_dir / "screenshot.png"
                screenshot(page, ss_path)
                ss_info = storage.persist_artifact(run_id, kind="screenshot", path=ss_path)
                self.log_event(
                    run_id,
                    step="artifact.screenshot",
                    status="ok",
                    details={"path": str(ss_path), "sha256": ss_info["sha256"]},
                    artifact_paths=[str(ss_path)],
                    output_digest=ss_info["sha256"],
                )
            else:
                self.log_event(run_id, step="artifact.screenshot_skipped", status="ok", details={"reason": "disabled_by_flag"})

            # ATS pivot: if linkedin gated or description short, or we see links
            links = find_external_apply_links(page)
            if links:
                max_try = int(settings.ats.get("max_links_to_try", 2))
                self.log_event(run_id, step="detect.apply_links", status="ok", details={"links_found": links[:max_try]})
                for link in links[:max_try]:
                    if not is_ats_url(link):
                        continue
                    from_host, to_host = h, url_host(link)
                    goto_with_retry(page, link, timeout_ms=int(settings.playwright.get("nav_timeout_ms", 15000)))
                    # Re-detect platform
                    guess2 = url_guess(link)
                    probe2 = probe_platform(page)
                    plat = probe2 if probe2.name != "other" else guess2
                    self.log_event(run_id, step="pivot.ats", status="ok", details={"from_host": from_host, "to_host": to_host, "url": link})
                    break

            # Extract fields
            # LLM flag: can be disabled via config or CLI; NavigatorAgent may set self.llm_enabled
            llm_enabled = bool(settings.llm.get("enabled", True)) and getattr(self, "_llm_enabled_override", True)
            # make run_id visible for extractor audit logging
            self._last_run_id = run_id
            fields, audit = extract_fields(page, plat.name, url, llm_enabled=llm_enabled, agent=self)
            self.log_event(
                run_id,
                step="extract.fields",
                status="ok",
                details=audit,
            )
            if not llm_enabled:
                self.log_event(run_id, step="llm.assist.skipped", status="ok", details={"reason": "disabled"})

            # Normalize
            norm = normalize_fields(fields)
            self.log_event(
                run_id,
                step="normalize.fields",
                status="ok",
                details={"transforms": list(norm.keys()), "content_hash": norm["content_hash"]},
                output_digest=norm["content_hash"],
            )

            # Persist job record
            job = JobRecord(
                run_id=run_id,
                url=url,
                platform=plat.name,
                title=norm["title"],
                company=norm["company"],
                location=norm["location"],
                description_text=norm["description_text"],
                detected_fields=norm["detected_fields"],
                extracted_at=None,
                content_hash=norm["content_hash"],
            )
            job_path = run_dir / "job_record.json"
            job_json = orjson.dumps(job.model_dump(), option=orjson.OPT_SORT_KEYS)
            job_path.write_bytes(job_json)
            jr_info = storage.persist_artifact(run_id, kind="job_record", path=job_path)
            self.log_event(
                run_id,
                step="persist.json",
                status="ok",
                details={"path": str(job_path), "sha256": jr_info["sha256"]},
                artifact_paths=[str(job_path)],
                output_digest=jr_info["sha256"],
            )

            job_id = storage.upsert_job(run_id, url, norm["content_hash"])  # idempotent
            self.log_event(
                run_id,
                step="persist.sqlite",
                status="ok",
                details={"job_id": job_id},
            )

            storage.finish_run(run_id, status="ok", error_message=None)
            self.log_event(
                run_id,
                step="run_finished",
                status="ok",
                details={}
            )
            return job

        except Exception as exc:
            tb_text = traceback.format_exc()
            tb_digest = sha256_bytes(tb_text.encode("utf-8"))
            self.log_event(
                run_id,
                step="run_failed",
                status="error",
                details={"error_type": type(exc).__name__, "error_message": str(exc), "traceback_digest": tb_digest},
            )
            storage.finish_run(run_id, status="error", error_message=str(exc))
            raise
        finally:
            try:
                if page:
                    page.close()
                if context:
                    context.close()
                if browser:
                    browser.close()
                if pw:
                    pw.stop()
            except Exception:
                pass
