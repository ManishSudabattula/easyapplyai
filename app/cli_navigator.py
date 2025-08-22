from __future__ import annotations

import argparse
import orjson

from .navigator import NavigatorAgent
from .settings import settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Navigator Agent CLI")
    parser.add_argument("--url", required=True, help="Job URL")
    parser.add_argument("--fixture", help="Path to HTML fixture to load instead of live nav")
    parser.add_argument("--headful", action="store_true", help="Run browser non-headless for this run")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM assist for this run")
    parser.add_argument("--no-screenshot", action="store_true", help="Skip taking a screenshot")
    parser.add_argument("--timeout", type=int, help="Navigation timeout override in ms")
    parser.add_argument("--no-html", action="store_true", help="Do not write raw.before/after HTML")
    args = parser.parse_args(argv)

    agent = NavigatorAgent()
    try:
        # Thread overrides
        if args.no_llm:
            setattr(agent, "_llm_enabled_override", False)
        if args.no_screenshot:
            setattr(agent, "_screenshot_enabled", False)
        if args.timeout:
            settings.playwright["nav_timeout_ms"] = int(args.timeout)
        if args.no_html:
            settings.artifacts["keep_raw_before_after"] = False
        job = agent.run(url=args.url, fixture_path=args.fixture, headless=(not args.headful))
        summary = {
            "artifacts_dir": str(settings.artifacts_dir_for(job.run_id)),
            "job_record": str(settings.artifacts_dir_for(job.run_id) / "job_record.json"),
            "run_id": job.run_id,
            "platform": job.platform,
            "url_final": job.url,
            "content_hash": job.content_hash,
            "status": "ok",
        }
        print(orjson.dumps(summary, option=orjson.OPT_SORT_KEYS).decode())
        return 0
    except Exception as _:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
