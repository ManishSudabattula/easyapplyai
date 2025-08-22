from __future__ import annotations

import argparse
import orjson

from .auth import SessionManager, AuthGateDetector
from .browser import open_persistent, goto_with_retry, export_storage_state
from .urltools import host as url_host


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manual auth and save session state")
    parser.add_argument("--url", required=True)
    args = parser.parse_args(argv)

    h = url_host(args.url)
    sess = SessionManager()
    auth = AuthGateDetector()

    pw = browser = context = page = None
    try:
        pw, browser, context, page = open_persistent(headless=False, storage_state=sess.load_state(h))
        goto_with_retry(page, args.url, timeout_ms=30000)
        print(f"Login window opened for {h}. Complete login, then press Enter to save session.")
        input()
        if auth.is_logged_in(page, h):
            state = export_storage_state(context)
            p = sess.save_state(h, state)
            print(orjson.dumps({"host": h, "saved": True, "path": str(p)}).decode())
        else:
            print(orjson.dumps({"host": h, "saved": False}).decode())
        return 0
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


if __name__ == "__main__":
    raise SystemExit(main())
