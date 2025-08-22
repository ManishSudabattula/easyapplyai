from __future__ import annotations

import json
from pathlib import Path

from app.navigator import NavigatorAgent
from app.settings import settings


def test_navigator_run_finishes(tmp_path: Path):
    settings.artifacts_base_dir = str(tmp_path)
    agent = NavigatorAgent()
    job = agent.run(url="https://example.com/jobs/123", fixture_path=str(Path("tests/fixtures/other.html")), headless=True)
    audit_path = settings.artifacts_dir_for(job.run_id) / "audit.jsonl"
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines, "audit should not be empty"
    last = json.loads(lines[-1])
    assert last["step"] == "run_finished"
    assert last["status"] == "ok"
    # ensure no AttributeError was raised (the test would have failed), sanity check content
    assert (settings.artifacts_dir_for(job.run_id) / "job_record.json").exists()
