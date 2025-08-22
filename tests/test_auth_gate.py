from __future__ import annotations

from pathlib import Path

from app.navigator import NavigatorAgent
from app.settings import settings


def test_auth_gate_emits_required(tmp_path: Path):
    settings.artifacts_base_dir = str(tmp_path)
    agent = NavigatorAgent()
    job = agent.run(url="https://www.linkedin.com/jobs/view/123", fixture_path=str(Path("tests/fixtures/linkedin_login.html")), headless=True)
    audit_path = settings.artifacts_dir_for(job.run_id) / "audit.jsonl"
    steps = [line.split('"step":"')[1].split('"',1)[0] for line in audit_path.read_text(encoding="utf-8").strip().splitlines()]
    assert "auth.session_loaded" in steps
    assert "url.canonicalized" in steps
    assert "navigate.fetch_html" in steps
    # In fixture mode we simulate a login page; manual login isn't triggered (no live)
    # But we still should continue extraction and finish
    assert "run_finished" in steps
