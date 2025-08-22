from __future__ import annotations

from pathlib import Path
import json

from app.navigator import NavigatorAgent
from app.settings import settings
from app import storage


def _run_fixture(fixture_name: str, url: str):
    agent = NavigatorAgent()
    return agent.run(url=url, fixture_path=str(Path("tests/fixtures") / fixture_name), headless=True)


def test_navigator_linkedin(tmp_path: Path):
    settings.artifacts_base_dir = str(tmp_path)
    job = _run_fixture("linkedin.html", "https://www.linkedin.com/jobs/view/123")
    run_dir = settings.artifacts_dir_for(job.run_id)
    assert (run_dir / "raw.html").exists()
    assert (run_dir / "screenshot.png").exists()
    assert (run_dir / "job_record.json").exists()
    assert (run_dir / "audit.jsonl").exists()
    assert job.platform == "linkedin"


def test_navigator_lever(tmp_path: Path):
    settings.artifacts_base_dir = str(tmp_path)
    job = _run_fixture("lever.html", "https://jobs.lever.co/acme/123")
    run_dir = settings.artifacts_dir_for(job.run_id)
    assert (run_dir / "raw.html").exists()
    assert (run_dir / "screenshot.png").exists()
    assert (run_dir / "job_record.json").exists()
    assert job.platform == "lever"


def test_navigator_greenhouse(tmp_path: Path):
    settings.artifacts_base_dir = str(tmp_path)
    job = _run_fixture("greenhouse.html", "https://boards.greenhouse.io/globex/jobs/123")
    run_dir = settings.artifacts_dir_for(job.run_id)
    assert (run_dir / "raw.html").exists()
    assert (run_dir / "screenshot.png").exists()
    assert (run_dir / "job_record.json").exists()
    assert job.platform == "greenhouse"


def test_navigator_other(tmp_path: Path):
    settings.artifacts_base_dir = str(tmp_path)
    job = _run_fixture("other.html", "https://example.com/jobs/123")
    run_dir = settings.artifacts_dir_for(job.run_id)
    assert (run_dir / "raw.html").exists()
    assert (run_dir / "screenshot.png").exists()
    assert (run_dir / "job_record.json").exists()
    assert job.platform == "other"


def test_navigator_audit_and_jobs(tmp_path: Path):
    settings.artifacts_base_dir = str(tmp_path)
    url = "https://jobs.lever.co/acme/123"
    job1 = _run_fixture("lever.html", url)
    job2 = _run_fixture("lever.html", url)  # idempotent
    # Check audit events written
    audit_path = settings.artifacts_dir_for(job1.run_id) / "audit.jsonl"
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    # Expect at least these steps
    required_steps = {
        "run_started",
        "navigate.fetch_html",
        "artifact.screenshot",
        "detect_platform.url_pattern",
        "detect_platform.dom_probe",
        "extract.fields",
        "normalize.fields",
        "persist.sqlite",
        "persist.json",
        "run_finished",
    }
    steps = {json.loads(l)["step"] for l in lines}
    assert required_steps.issubset(steps)

    # Jobs table: just one row for same (url, content_hash)
    # Not directly exposed; we can ensure upsert didn't throw and content_hash consistent
    assert job1.content_hash == job2.content_hash
