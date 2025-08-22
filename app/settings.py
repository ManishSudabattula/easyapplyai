from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import orjson
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_PATH = _PROJECT_ROOT / "config" / "config.json"


class _ArtifactsCfg(BaseModel):
    base_dir: str
    keep_raw_before_after: bool = True
    compress_html: bool = False


class _RetriesCfg(BaseModel):
    max_attempts: int
    backoff_initial_ms: int
    backoff_max_ms: int


class _LLMCfg(BaseModel):
    provider: str
    model_primary: str
    temperature: float
    top_p: float
    max_tokens: int
    request_timeout_s: int


class _RawConfig(BaseModel):
    artifacts: _ArtifactsCfg
    retries: _RetriesCfg
    llm: _LLMCfg
    playwright: Optional[Dict[str, Any]] = None
    auth: Optional[Dict[str, Any]] = None
    expand: Optional[Dict[str, Any]] = None
    ats: Optional[Dict[str, Any]] = None


class Settings(BaseModel):
    artifacts_base_dir: str = Field(..., description="Base directory for artifacts")
    artifacts: Dict[str, Any]
    retries: Dict[str, Any]
    llm: Dict[str, Any]
    playwright: Dict[str, Any]
    auth: Dict[str, Any]
    expand: Dict[str, Any]
    ats: Dict[str, Any]

    @classmethod
    def load(cls) -> "Settings":
        # Load environment variables
        load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=False)

        # Load and validate config
        try:
            raw_bytes = _CONFIG_PATH.read_bytes()
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Missing config file at {_CONFIG_PATH}") from e
        try:
            raw_obj = orjson.loads(raw_bytes)
        except orjson.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {_CONFIG_PATH}") from e
        try:
            validated = _RawConfig.model_validate(raw_obj)
        except ValidationError as e:
            raise ValueError(f"Invalid config structure: {e}") from e

        # Defaults for optional sections
        playwright_cfg = {
            "headless": True,
            "nav_timeout_ms": 15000,
            "wait_timeout_ms": 15000,
            "screenshot_full_page": True,
        }
        if validated.playwright:
            playwright_cfg.update(validated.playwright)

        # Defaults for auth
        auth_cfg = {
            "sessions_dir": "sessions",
            "allow_manual_login": True,
            "manual_login_timeout_s": 420,
            "domains": {},
        }
        if validated.auth:
            auth_cfg.update(validated.auth)

        # Defaults for expanders
        expand_cfg = {
            "max_clicks": 4,
            "stabilize_ms": 700,
            "min_delta_chars": 200,
            "selectors": {
                "linkedin": [],
                "lever": [],
                "greenhouse": [],
                "generic": [],
            },
        }
        if validated.expand:
            expand_cfg.update(validated.expand)

        # Defaults for ATS
        ats_cfg = {
            "known_hosts": [],
            "max_links_to_try": 2,
        }
        if validated.ats:
            ats_cfg.update(validated.ats)

        settings = cls(
            artifacts_base_dir=validated.artifacts.base_dir,
            artifacts=validated.artifacts.model_dump(),
            retries=validated.retries.model_dump(),
            llm=validated.llm.model_dump(),
            playwright=playwright_cfg,
            auth=auth_cfg,
            expand=expand_cfg,
            ats=ats_cfg,
        )
        return settings

    @property
    def cfg_hash(self) -> str:
        from hashlib import sha256

        # Canonicalize raw config JSON (not the flattened Settings)
        try:
            raw_bytes = _CONFIG_PATH.read_bytes()
        except FileNotFoundError:
            raw_bytes = b"{}"
        # Re-serialize canonically to avoid ordering differences from authoring
        try:
            obj = orjson.loads(raw_bytes)
        except orjson.JSONDecodeError:
            obj = {}
        canonical = orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
        return sha256(canonical).hexdigest()

    def artifacts_dir_for(self, run_id: str) -> Path:
        base = Path(self.artifacts_base_dir)
        # Resolve relative to project root if relative path provided
        if not base.is_absolute():
            base = _PROJECT_ROOT / base
        run_dir = base / run_id
        # Ensure directories exist
        base.mkdir(parents=True, exist_ok=True)
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def sessions_dir(self) -> Path:
        base = self.auth.get("sessions_dir", "sessions")
        p = Path(base)
        if not p.is_absolute():
            p = _PROJECT_ROOT / p
        p.mkdir(parents=True, exist_ok=True)
        return p


# Singleton settings instance for convenience
settings = Settings.load()
