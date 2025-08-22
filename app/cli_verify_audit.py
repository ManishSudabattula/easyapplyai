from __future__ import annotations

import argparse
import json
from pathlib import Path

import orjson


def verify_chain(audit_path: Path) -> dict:
    from app.hashing import chain_next
    events = []
    prev = ""
    break_index = -1
    for idx, line in enumerate(audit_path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        ev = json.loads(line)
        expected_prev = prev
        if ev.get("prev_event_hash", "") != expected_prev:
            break_index = idx
            break
        payload = {k: ev[k] for k in ev.keys() if k != "event_hash"}
        recomputed = chain_next(ev.get("prev_event_hash", ""), payload)
        if recomputed != ev.get("event_hash"):
            break_index = idx
            break
        prev = ev.get("event_hash")
        events.append(ev)
    return {
        "run_id": events[0]["run_id"] if events else None,
        "events": len(events),
        "valid": break_index == -1,
        "break_index": None if break_index == -1 else break_index,
    }


essage = """
Usage: python -m app.cli_verify_audit --run <run_id_or_path>
- If a directory is provided, it will look for audit.jsonl in it.
- If a run_id is provided, it will resolve to artifacts/<run_id>/audit.jsonl.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify audit log hash chain")
    parser.add_argument("--run", required=True)
    args = parser.parse_args(argv)

    target = Path(args.run)
    if target.is_dir():
        audit = target / "audit.jsonl"
    else:
        from app.settings import settings
        base = settings.artifacts_dir_for(args.run)
        audit = base / "audit.jsonl"
    if not audit.exists():
        print(orjson.dumps({"valid": False, "error": "audit.jsonl not found", "path": str(audit)}).decode())
        return 2
    result = verify_chain(audit)
    print(orjson.dumps(result, option=orjson.OPT_SORT_KEYS).decode())
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
