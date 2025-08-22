from __future__ import annotations

from typing import Dict, List, Tuple
from urllib.parse import urlparse
import orjson
from bs4 import BeautifulSoup


def _get_meta_content(page, selector: str) -> str:
    try:
        return page.evaluate(
            "selector => (document.querySelector(selector) || {}).content || ''",
            selector,
        ) or ""
    except Exception:
        return ""


def first_text(page, selectors: List[str]) -> Tuple[str, str]:
    """Return (text, selector_used)."""
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                # innerText preserves layout
                txt = el.inner_text().strip()
                if txt:
                    return txt, sel
        except Exception:
            continue
    return "", ""


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    # Replace list items with bullets
    for li in soup.select("li"):
        li.insert_before("\n• ")
    # Remove scripts/styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    # Collapse whitespace
    return " ".join(text.split())


_SELECTOR_PACKS = {
    "linkedin": {
        "title": ['h1[data-test-job-title]', 'h1.top-card-layout__title'],
        "company": ['.topcard__org-name-link', 'a[data-tracking-control-name="public_jobs_topcard-org-name"]'],
        "location": ['.topcard__flavor--bullet', '.topcard__flavor--metadata'],
        "desc_root": [
            "section:has(h2:has-text(\"About the job\"))",
            'div.show-more-less-html__markup',
            '#job-details',
            '.jobs-description__content',
        ],
    },
    "lever": {
        "title": ['.posting-headline h2', '.posting-header h2', 'h1'],
        "company": ['meta[property="og:site_name"]'],
        "location": ['.posting-categories .location', '.location'],
        "desc_root": ['.section-wrapper.description', '.content', '.posting'],
    },
    "greenhouse": {
        "title": ['h1.app-title', '#content h1', 'h1'],
        "company": ['meta[property="og:site_name"]'],
        "location": ['.location', '.app-location'],
        "desc_root": ['#content', '.opening', '.job'],
    },
    "other": {
        "title": ['h1'],
        "company": ['meta[property="og:site_name"]'],
        "location": ['.location', '#location'],
        "desc_root": ['main', 'article', '#content', '.content', 'body'],
    },
}


def _company_from_meta_or_host(page, url: str) -> str:
    meta = _get_meta_content(page, 'meta[property="og:site_name"]')
    if meta:
        return meta.strip()
    try:
        host = urlparse(url).hostname or ""
        parts = host.split('.')
        if len(parts) >= 2:
            return parts[-2].capitalize()
        return host
    except Exception:
        return ""


def extract_fields(page, platform_name: str, url: str, llm_enabled: bool = True, agent=None) -> Tuple[Dict, Dict]:
    packs = _SELECTOR_PACKS
    pack = packs.get(platform_name, packs["other"])  # type: ignore

    used = {}
    missing = []

    title, sel_t = first_text(page, pack["title"])  # type: ignore
    if title:
        used["title"] = sel_t

    comp = ""
    if 'meta[property="og:site_name"]' in pack["company"]:
        comp = _company_from_meta_or_host(page, url)
        if comp:
            used["company"] = 'meta[property="og:site_name"]'
    if not comp:
        comp, sel_c = first_text(page, [s for s in pack["company"] if s != 'meta[property="og:site_name"]'])
        if comp:
            used["company"] = sel_c

    location, sel_l = first_text(page, pack["location"])  # type: ignore
    if location:
        used["location"] = sel_l

    desc_html = ""
    for sel in pack["desc_root"]:  # type: ignore
        el = None
        try:
            el = page.query_selector(sel)
        except Exception:
            pass
        if el:
            try:
                desc_html = el.inner_html()
            except Exception:
                try:
                    desc_html = el.text_content()
                except Exception:
                    desc_html = ""
            if desc_html:
                used["description_root"] = sel
                break
    description_text = html_to_text(desc_html)

    fields = {
        "title": title or "",
        "company": comp or "",
        "location": location or "",
        "description_text": description_text or "",
        "detected_fields": used,
    }

    for key in ["title", "company", "location", "description_text"]:
        if not fields[key]:
            missing.append(key)

    audit = {
        "selectors_used": used,
        "missing": missing,
        "llm_used": False,
    }
    # LLM assist if enabled and missing
    missing_keys: List[str] = [k for k in ["title", "company", "location", "description_text"] if not (fields.get(k) or "").strip()]
    # Treat truncated description as missing
    if fields.get("description_text", "").strip().endswith("…") or fields.get("description_text", "").strip().endswith("..."):
        if "description_text" not in missing_keys:
            missing_keys.append("description_text")

    if llm_enabled and missing_keys:
        from .settings import settings
        from .llm_client import infer_fields, redact_hashes
        from .prompts import build_infer_prompt

        # Build context: prefer description root text, else whole page text limited
        ctx_text = page.inner_text("body")[:30000]
        prompt = build_infer_prompt(missing_keys, platform_name, url)
        hashes = redact_hashes(prompt, ctx_text, "")
        if agent:
            agent.log_event(
                run_id=agent._last_run_id,  # relies on NavigatorAgent to set
                step="llm.assist.request",
                status="ok",
                details={
                    "missing": missing_keys,
                    "prompt_sha256": hashes["prompt_sha256"],
                    "context_sha256": hashes["context_sha256"],
                    "model_name": settings.llm.get("model_primary"),
                },
            )
        try:
            resp = infer_fields(missing_keys, ctx_text, platform_name, page_url=url)
            # Validate grounding: values must appear in context (case-insensitive substring) except trivial whitespace diffs
            filled, empty, discarded = [], [], []
            low_ctx = ctx_text.lower()
            for k in missing_keys:
                val = (resp.get(k) or "").strip()
                if not val:
                    empty.append(k)
                    continue
                if k != "description_text" and val.lower() not in low_ctx:
                    discarded.append(k)
                    continue
                fields[k] = val
                filled.append(k)
            details_resp = redact_hashes(prompt, ctx_text, orjson.dumps(resp).decode())
            if agent:
                agent.log_event(
                    run_id=agent._last_run_id,
                    step="llm.assist.response",
                    status="ok",
                    details={
                        "filled": filled,
                        "empty": empty,
                        "response_sha256": details_resp["response_sha256"],
                    },
                )
                if discarded:
                    agent.log_event(
                        run_id=agent._last_run_id,
                        step="llm.assist.discarded",
                        status="ok",
                        details={"keys": discarded, "reason": "not_in_context"},
                    )
        except Exception as e:
            if agent:
                agent.log_event(
                    run_id=agent._last_run_id,
                    step="llm.assist.error",
                    status="error",
                    details={"error_type": type(e).__name__, "message": str(e)},
                )

    return fields, audit


def description_roots_for(platform_name: str) -> List[str]:
    packs = _SELECTOR_PACKS
    pack = packs.get(platform_name, packs["other"])  # type: ignore
    return pack["desc_root"]  # type: ignore
