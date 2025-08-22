from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Dict, Any
import orjson


def sha256_bytes(b: bytes) -> str:
    """Return hex sha256 of bytes."""
    h = sha256()
    h.update(b)
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    """Return hex sha256 of a file's contents."""
    h = sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def chain_next(prev_hash: str, payload: Dict[str, Any]) -> str:
    """Compute the next link in a hash chain.

    Serialize payload deterministically (sorted keys), then compute
    sha256(prev_hash_bytes + payload_json_bytes).
    """
    if prev_hash is None:
        prev_hash = ""
    if not isinstance(prev_hash, str):
        raise TypeError("prev_hash must be a string")
    payload_bytes = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    h = sha256()
    h.update(prev_hash.encode("utf-8"))
    h.update(payload_bytes)
    return h.hexdigest()
