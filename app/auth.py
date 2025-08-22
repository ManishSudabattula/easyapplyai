from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Any

from pydantic import BaseModel

from .settings import settings


class SessionManager:
    def __init__(self) -> None:
        self._dir = settings.sessions_dir()

    def state_path_for(self, host: str) -> Path:
        safe = host.replace(":", "_")
        return self._dir / f"{safe}.json"

    def load_state(self, host: str) -> Optional[Dict[str, Any]]:
        p = self.state_path_for(host)
        if p.exists():
            try:
                import orjson
                return orjson.loads(p.read_bytes())
            except Exception:
                return None
        return None

    def save_state(self, host: str, storage_state: Dict[str, Any]) -> Path:
        import orjson
        p = self.state_path_for(host)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(orjson.dumps(storage_state))
        return p


class AuthGateDetector:
    def __init__(self) -> None:
        self.domains = settings.auth.get("domains", {})

    def _get_cfg(self, host: str) -> Dict[str, Any]:
        return self.domains.get(host, {})

    def is_login_gate(self, page, host: str) -> bool:
        cfg = self._get_cfg(host)
        selectors = cfg.get("login_markers", [])
        for sel in selectors:
            try:
                if page.query_selector(sel):
                    return True
            except Exception:
                continue
        return False

    def is_logged_in(self, page, host: str) -> bool:
        cfg = self._get_cfg(host)
        selectors = cfg.get("logged_in_markers", [])
        for sel in selectors:
            try:
                if page.query_selector(sel):
                    return True
            except Exception:
                continue
        return False
