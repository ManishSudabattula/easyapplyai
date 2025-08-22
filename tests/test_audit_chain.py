from __future__ import annotations

from pathlib import Path

from app.audit import AuditTrailAgent
from app import storage
from app.settings import settings


def test_audit_chain(tmp_path: Path):
    # Redirect artifacts to temp dir
    settings.artifacts_base_dir = str(tmp_path)

    run_id = storage.create_run("https://example.com/job1")
    agent = AuditTrailAgent()

    e1 = agent.log_event(run_id, "step1", "ok", details={})
    e2 = agent.log_event(run_id, "step2", "ok", details={})
    e3 = agent.log_event(run_id, "step3", "ok", details={})

    assert e2.prev_event_hash == e1.event_hash
    assert e3.prev_event_hash == e2.event_hash

    audit_log = Path(settings.artifacts_dir_for(run_id)) / "audit.jsonl"
    assert audit_log.exists()
    lines = audit_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 3
