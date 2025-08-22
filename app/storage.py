from __future__ import annotations

import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import orjson
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    create_engine,
    select,
    update,
)
from sqlalchemy.orm import declarative_base, sessionmaker
import datetime as _dt

from .schemas import AuditEvent
from .hashing import sha256_file

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DB_PATH = _PROJECT_ROOT / "automation.db"

# Ensure parent exists (project root should exist)
engine = create_engine(f"sqlite:///{_DB_PATH}", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat()


class Run(Base):
    __tablename__ = "runs"
    run_id = Column(String, primary_key=True)
    url = Column(Text, nullable=False)
    started_at = Column(String, nullable=False)
    finished_at = Column(String, nullable=True)
    status = Column(String, nullable=False)
    error_message = Column(Text, nullable=True)


class Artifact(Base):
    __tablename__ = "artifacts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, nullable=False)
    kind = Column(String, nullable=False)
    path = Column(Text, nullable=False)
    sha256 = Column(String, nullable=False)
    created_at = Column(String, nullable=False)


class Audit(Base):
    __tablename__ = "audit"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, nullable=False)
    step = Column(String, nullable=False)
    status = Column(String, nullable=False)
    ts_iso = Column(String, nullable=False)
    ts_ns = Column(Integer, nullable=False)
    input_digest = Column(String, nullable=True)
    output_digest = Column(String, nullable=True)
    prev_event_hash = Column(String, nullable=False)
    event_hash = Column(String, nullable=False)
    details_json = Column(Text, nullable=False)


class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, nullable=False)
    url = Column(Text, nullable=False)
    content_hash = Column(String, nullable=True)
    extracted_at = Column(String, nullable=True)


# Create tables if they do not exist
Base.metadata.create_all(engine)


def create_run(url: str) -> str:
    run_id = str(uuid.uuid4())
    with SessionLocal() as session:
        session.add(
            Run(
                run_id=run_id,
                url=url,
                started_at=_utc_now_iso(),
                finished_at=None,
                status="running",
                error_message=None,
            )
        )
        session.commit()
    return run_id


def finish_run(run_id: str, status: str, error_message: Optional[str] = None) -> None:
    with SessionLocal() as session:
        stmt = (
            update(Run)
            .where(Run.run_id == run_id)
            .values(
                finished_at=_utc_now_iso(),
                status=status,
                error_message=error_message,
            )
        )
        session.execute(stmt)
        session.commit()


def persist_artifact(run_id: str, kind: str, path: Path) -> Dict[str, Any]:
    sha = sha256_file(path)
    created_at = _utc_now_iso()
    with SessionLocal() as session:
        art = Artifact(run_id=run_id, kind=kind, path=str(path), sha256=sha, created_at=created_at)
        session.add(art)
        session.commit()
        session.refresh(art)
        return {"id": art.id, "run_id": run_id, "kind": kind, "path": str(path), "sha256": sha, "created_at": created_at}


def append_audit(event: AuditEvent) -> None:
    with SessionLocal() as session:
        session.add(
            Audit(
                run_id=event.run_id,
                step=event.step,
                status=event.status,
                ts_iso=event.ts_iso,
                ts_ns=event.ts_ns,
                input_digest=event.input_digest,
                output_digest=event.output_digest,
                prev_event_hash=event.prev_event_hash,
                event_hash=event.event_hash,
                details_json=orjson.dumps(event.details, option=orjson.OPT_SORT_KEYS).decode(),
            )
        )
        session.commit()


# Helpers for agent/tests

def get_last_audit_hash(run_id: str) -> Optional[str]:
    with SessionLocal() as session:
        stmt = select(Audit).where(Audit.run_id == run_id).order_by(Audit.id.desc()).limit(1)
        row = session.execute(stmt).scalars().first()
        return row.event_hash if row else None


def get_artifact_count(run_id: str) -> int:
    with SessionLocal() as session:
        stmt = select(Artifact).where(Artifact.run_id == run_id)
        count = session.execute(stmt).scalars().all()
        return len(count)


def get_artifacts_for_run(run_id: str) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = select(Artifact).where(Artifact.run_id == run_id).order_by(Artifact.id.asc())
        rows = session.execute(stmt).scalars().all()
        return [
            {"id": r.id, "run_id": r.run_id, "kind": r.kind, "path": r.path, "sha256": r.sha256, "created_at": r.created_at}
            for r in rows
        ]


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    with SessionLocal() as session:
        row = session.get(Run, run_id)
        if not row:
            return None
        return {
            "run_id": row.run_id,
            "url": row.url,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "status": row.status,
            "error_message": row.error_message,
        }


def upsert_job(run_id: str, url: str, content_hash: str) -> int:
    """Insert job if (url, content_hash) pair not present; return id.

    Idempotent: if a row exists with same url+hash, return its id.
    """
    now = _utc_now_iso()
    with SessionLocal() as session:
        # find existing
        existing = session.execute(
            select(Job).where(Job.url == url, Job.content_hash == content_hash)
        ).scalars().first()
        if existing:
            return int(existing.id)
        job = Job(run_id=run_id, url=url, content_hash=content_hash, extracted_at=now)
        session.add(job)
        session.commit()
        session.refresh(job)
        return int(job.id)
