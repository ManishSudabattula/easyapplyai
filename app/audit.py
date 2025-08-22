from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, Any, Optional, List

import orjson

from .hashing import chain_next
from .schemas import AuditEvent
from .settings import settings
from . import storage


class AuditTrailAgent:
    def __init__(self) -> None:
        self._last_hash_by_run: Dict[str, str] = {}

    def _resolve_prev_hash(self, run_id: str) -> str:
        if run_id in self._last_hash_by_run:
            return self._last_hash_by_run[run_id]
        # Try to recover from DB
        last = storage.get_last_audit_hash(run_id)
        return last or ""

    def log_event(
        self,
        run_id: str,
        step: str,
        status: str,
        details: Dict[str, Any],
        input_digest: Optional[str] = None,
        output_digest: Optional[str] = None,
        artifact_paths: Optional[List[str]] = None,
    ) -> AuditEvent:
        if artifact_paths is None:
            artifact_paths = []
        ts_iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
        # Include fractional seconds with UTC 'Z'
        ts_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        ts_ns = time.perf_counter_ns()

        prev_hash = self._resolve_prev_hash(run_id)

        # Build event without event_hash first
        event_dict = {
            "run_id": run_id,
            "step": step,
            "status": status,
            "ts_iso": ts_iso,
            "ts_ns": ts_ns,
            "input_digest": input_digest,
            "output_digest": output_digest,
            "artifact_paths": artifact_paths,
            "details": details,
            "prev_event_hash": prev_hash,
        }
        event_hash = chain_next(prev_hash, event_dict)
        event_full = AuditEvent(**{**event_dict, "event_hash": event_hash})

        # Write to audit.jsonl under artifacts dir
        run_dir = settings.artifacts_dir_for(run_id)
        audit_path = run_dir / "audit.jsonl"
        line = orjson.dumps(event_full.model_dump(), option=orjson.OPT_SORT_KEYS)
        with open(audit_path, "ab") as f:
            f.write(line + b"\n")

        # Persist to DB
        storage.append_audit(event_full)

        # Update in-memory last hash
        self._last_hash_by_run[run_id] = event_hash

        return event_full
