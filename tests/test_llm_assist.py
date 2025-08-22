from __future__ import annotations

from pathlib import Path
import json

from app.settings import settings
from app.navigator import NavigatorAgent


def test_llm_assist_fills_missing_company(monkeypatch, tmp_path: Path):
    settings.artifacts_base_dir = str(tmp_path)

    # Stub llm_client.infer_fields
    import app.llm_client as llm

    def fake_infer(missing, context_text, platform, page_url=None):
        return {k: ("Acme AI" if k == "company" else "") for k in missing}

    monkeypatch.setattr(llm, "infer_fields", fake_infer)

    agent = NavigatorAgent()
    job = agent.run(url="https://www.linkedin.com/jobs/view/123", fixture_path=str(Path("tests/fixtures/missing_company.html")), headless=True)
    audit_path = settings.artifacts_dir_for(job.run_id) / "audit.jsonl"
    lines = [json.loads(l) for l in audit_path.read_text(encoding="utf-8").splitlines()]
    steps = [e["step"] for e in lines]
    assert "llm.assist.request" in steps
    assert "llm.assist.response" in steps
    # Ensure no raw prompt/context present
    joined = audit_path.read_text(encoding="utf-8")
    assert "CONTEXT:" not in joined


def test_llm_assist_skipped_flag(monkeypatch, tmp_path: Path):
    settings.artifacts_base_dir = str(tmp_path)
    agent = NavigatorAgent()
    setattr(agent, "_llm_enabled_override", False)
    job = agent.run(url="https://jobs.lever.co/acme/123", fixture_path=str(Path("tests/fixtures/missing_title.html")), headless=True)
    audit_path = settings.artifacts_dir_for(job.run_id) / "audit.jsonl"
    steps = [json.loads(l)["step"] for l in audit_path.read_text(encoding="utf-8").splitlines()]
    assert "llm.assist.skipped" in steps
