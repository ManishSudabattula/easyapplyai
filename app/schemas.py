from __future__ import annotations

from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    run_id: str
    step: str
    status: Literal["ok", "error"]
    ts_iso: str  # UTC ISO 8601
    ts_ns: int   # monotonic clock nanoseconds
    input_digest: Optional[str] = None
    output_digest: Optional[str] = None
    artifact_paths: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)
    prev_event_hash: str
    event_hash: str


class RunSummary(BaseModel):
    run_id: str
    url: str
    started_at: str
    finished_at: Optional[str]
    status: str
    error_message: Optional[str] = None


class JobRecord(BaseModel):
    run_id: str
    url: str
    platform: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    description_text: Optional[str] = None
    detected_fields: Dict[str, Any] = Field(default_factory=dict)
    extracted_at: Optional[str] = None
    content_hash: Optional[str] = None
