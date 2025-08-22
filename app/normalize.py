from __future__ import annotations

import re
from typing import Dict

from .hashing import sha256_bytes


_ws_re = re.compile(r"\s+")


def normalize_ws(s: str) -> str:
    return _ws_re.sub(" ", (s or "").strip())


def tidy_title(s: str) -> str:
    return normalize_ws(s)


def tidy_company(s: str) -> str:
    s = normalize_ws(s)
    s = re.sub(r"\s*[–-]\s*Careers\b", "", s, flags=re.I)
    s = re.sub(r"\s+at\s+.+$", "", s, flags=re.I)
    return s.strip()


def tidy_location(s: str) -> str:
    s = normalize_ws(s)
    s = re.sub(r"\s*,\s*", ", ", s)
    return s


def compute_content_hash(title: str, company: str, location: str, description_text: str) -> str:
    joined = "\n".join([
        normalize_ws(title),
        normalize_ws(company),
        normalize_ws(location),
        normalize_ws(description_text),
    ])
    return sha256_bytes(joined.encode("utf-8"))


def normalize_fields(fields: Dict) -> Dict:
    title = tidy_title(fields.get("title", ""))
    company = tidy_company(fields.get("company", ""))
    location = tidy_location(fields.get("location", ""))
    description_text = normalize_ws(fields.get("description_text", ""))
    content_hash = compute_content_hash(title, company, location, description_text)
    return {
        "title": title,
        "company": company,
        "location": location,
        "description_text": description_text,
        "detected_fields": fields.get("detected_fields", {}),
        "content_hash": content_hash,
    }
