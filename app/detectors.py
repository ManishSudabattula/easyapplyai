from __future__ import annotations

import re
from typing import List, Literal
from pydantic import BaseModel, Field

from .settings import settings
from .urltools import ats_host_of


PlatformName = Literal["linkedin", "lever", "greenhouse", "other"]


class DetectedPlatform(BaseModel):
    name: PlatformName
    confidence: float = 0.0
    matched_selectors: List[str] = Field(default_factory=list)


_URL_PATTERNS = {
    "linkedin": re.compile(r"(www\.)?linkedin\.com/jobs/view", re.I),
    "lever": re.compile(r"jobs\.lever\.co/", re.I),
    "greenhouse": re.compile(r"(boards\.)?greenhouse\.io/", re.I),
}

_PROBES = {
    "linkedin": [
        'h1[data-test-job-title]',
        'h1.top-card-layout__title',
        '[data-test="job-details"]',
        '.top-card-layout__entity-info',
    ],
    "lever": [
        '.posting-headline h2',
        '.posting-header h2',
        '.posting-categories .location',
        '.posting',
    ],
    "greenhouse": [
        'h1.app-title',
        '#content h1',
        '.opening .title',
        '.job h1',
    ],
}


def url_guess(url: str) -> DetectedPlatform:
    for name, pattern in _URL_PATTERNS.items():
        if pattern.search(url or ""):
            return DetectedPlatform(name=name, confidence=0.5)
    return DetectedPlatform(name="other", confidence=0.1)


def probe_platform(page) -> DetectedPlatform:
    scores = {}
    matched = []
    for name, selectors in _PROBES.items():
        hits = 0
        for sel in selectors:
            try:
                if page.query_selector(sel):
                    hits += 1
                    matched.append(sel)
            except Exception:
                continue
        if hits:
            scores[name] = hits
    if not scores:
        return DetectedPlatform(name="other", confidence=0.1, matched_selectors=matched)
    # Pick max hits
    best = max(scores.items(), key=lambda kv: kv[1])[0]
    total = sum(scores.values())
    conf = scores[best] / max(total, 1)
    return DetectedPlatform(name=best, confidence=conf, matched_selectors=matched)


def detect_platform(url: str, page) -> DetectedPlatform:
    guess = url_guess(url)
    probe = probe_platform(page)
    # Combine: prefer probe if it found something non-other
    if probe.name != "other":
        return probe
    return guess


_ATS_HOST_PATTERNS = re.compile(
    r"(" + r"|".join([re.escape(h) for h in settings.ats.get("known_hosts", [])]) + r")",
    re.I,
)


def _redact_query(url: str) -> str:
    try:
        from urllib.parse import urlparse, urlunparse

        p = urlparse(url)
        return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    except Exception:
        return url


def find_external_apply_links(page) -> List[str]:
    links: List[str] = []
    try:
        for a in page.query_selector_all("a[href], button[href]"):
            href = a.get_attribute("href") or ""
            text = (a.inner_text() or "").strip().lower()
            if _ATS_HOST_PATTERNS.search(href) or any(k in text for k in ["apply", "careers", "apply now", "apply on company"]):
                links.append(_redact_query(href))
    except Exception:
        pass
    # Deduplicate while preserving order
    seen = set()
    dedup = []
    for l in links:
        key = _redact_query(l)
        if key not in seen and ats_host_of(l):
            dedup.append(key)
            seen.add(key)
    return dedup


def is_ats_url(url: str) -> bool:
    return ats_host_of(url) is not None
