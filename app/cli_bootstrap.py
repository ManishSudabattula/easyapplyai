from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from pathlib import Path

import orjson

from .audit import AuditTrailAgent
from .hashing import sha256_bytes
from .settings import settings
from . import storage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local-first job app automation bootstrap")
    parser.add_argument("--url", required=True, help="Target job URL")
    args = parser.parse_args(argv)

    agent = AuditTrailAgent()
    start_perf_ns = time.perf_counter_ns()

    run_id = storage.create_run(args.url)
    run_dir = settings.artifacts_dir_for(run_id)

    try:
        agent.log_event(
            run_id,
            step="run_started",
            status="ok",
            details={"url": args.url, "cfg_hash": settings.cfg_hash},
            input_digest=None,
            output_digest=None,
            artifact_paths=[],
        )

        # Step 1: check env
        env_present = []
        if os.getenv("OPENROUTER_API_KEY"):
            env_present.append("OPENROUTER_API_KEY")
        agent.log_event(
            run_id,
            step="bootstrap.check_env",
            status="ok",
            details={"env_keys_present": env_present},
            input_digest=None,
            output_digest=None,
            artifact_paths=[],
        )

        # Step 2: write a placeholder artifact
        placeholder_path = run_dir / "placeholder.txt"
        placeholder_path.write_text("bootstrap placeholder\n", encoding="utf-8")
        art = storage.persist_artifact(run_id, kind="placeholder", path=placeholder_path)
        agent.log_event(
            run_id,
            step="bootstrap.write_placeholder_artifact",
            status="ok",
            details={"path": str(placeholder_path), "sha256": art["sha256"]},
            input_digest=None,
            output_digest=art["sha256"],
            artifact_paths=[str(placeholder_path)],
        )

        duration_ms = (time.perf_counter_ns() - start_perf_ns) // 1_000_000
        artifacts_count = storage.get_artifact_count(run_id)
        agent.log_event(
            run_id,
            step="run_finished",
            status="ok",
            details={"artifacts_count": artifacts_count, "duration_ms": int(duration_ms)},
            input_digest=None,
            output_digest=None,
            artifact_paths=[],
        )

        storage.finish_run(run_id, status="ok", error_message=None)

        summary = {
            "run_id": run_id,
            "status": "ok",
            "artifacts_dir": str(run_dir),
            "audit_log": str(run_dir / "audit.jsonl"),
        }
        print(orjson.dumps(summary, option=orjson.OPT_SORT_KEYS).decode())
        return 0

    except Exception as exc:
        tb_text = traceback.format_exc()
        tb_digest = sha256_bytes(tb_text.encode("utf-8"))
        try:
            agent.log_event(
                run_id,
                step="run_failed",
                status="error",
                details={
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "traceback_digest": tb_digest,
                },
                input_digest=None,
                output_digest=None,
                artifact_paths=[],
            )
        finally:
            storage.finish_run(run_id, status="error", error_message=str(exc))
            summary = {
                "run_id": run_id,
                "status": "error",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "artifacts_dir": str(settings.artifacts_dir_for(run_id)),
                "audit_log": str(settings.artifacts_dir_for(run_id) / "audit.jsonl"),
            }
            print(orjson.dumps(summary, option=orjson.OPT_SORT_KEYS).decode(), file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
