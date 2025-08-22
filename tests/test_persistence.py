from __future__ import annotations

from pathlib import Path

from app import storage
from app.hashing import sha256_file
from app.settings import settings


def test_persist_artifact_and_run_lifecycle(tmp_path: Path):
    # Use temp artifacts dir to avoid pollution
    settings.artifacts_base_dir = str(tmp_path)

    # Prepare a dummy file
    run_id = storage.create_run("https://example.com/job2")
    fpath = tmp_path / run_id / "dummy.txt"
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text("hello world\n", encoding="utf-8")

    # Persist and verify
    art = storage.persist_artifact(run_id, kind="text", path=fpath)
    rows = storage.get_artifacts_for_run(run_id)
    assert any(r["path"] == str(fpath) for r in rows)
    assert art["sha256"] == sha256_file(fpath)

    # Finish run and verify
    storage.finish_run(run_id, status="ok", error_message=None)
    run = storage.get_run(run_id)
    assert run is not None
    assert run["started_at"] is not None
    assert run["finished_at"] is not None
    assert run["status"] == "ok"
