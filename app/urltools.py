from __future__ import annotations

from urllib.parse import urlparse, urlunparse, parse_qs, urljoin
from typing import Optional
from .settings import settings


def host(url: str) -> str:
    try:
        return urlparse(url or "").hostname or ""
    except Exception:
        return ""


def canonicalize(url: str) -> str:
    """Canonicalize known job URLs (LinkedIn) and normalize generically.

    - linkedin collections recommended: .../jobs/collections/recommended?currentJobId=<id>
      -> https://www.linkedin.com/jobs/view/<id>/
    - strip tracking query params; keep only essential (none for now)
    - ensure trailing slash for linkedin /jobs/view/<id>/
    """
    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            return url
        netloc = parsed.netloc
        path = parsed.path
        query = parse_qs(parsed.query)
        if netloc.endswith("linkedin.com"):
            if "/jobs/collections/recommended" in path and "currentJobId" in query:
                job_id = query.get("currentJobId", [""])[0]
                if job_id:
                    return f"https://www.linkedin.com/jobs/view/{job_id}/"
            # normalize /jobs/view/<id> missing trailing slash
            if "/jobs/view/" in path and not path.endswith("/"):
                return urlunparse((parsed.scheme, parsed.netloc, path + "/", "", "", ""))
        # fallback: remove query/fragment and tracking
        return strip_tracking(urlunparse((parsed.scheme, parsed.netloc, path.rstrip('/'), "", "", "")))
    except Exception:
        return url


def prefer_meta_canonical(page) -> Optional[str]:
    try:
        link = page.eval_on_selector("link[rel=canonical]", "el => el && el.href || null")
        og = page.eval_on_selector("meta[property='og:url']", "el => el && el.content || null")
        cand = link or og
        if not cand:
            return None
        # Ensure same host
        cur = urlparse(page.url)
        tar = urlparse(cand)
        if tar.hostname and tar.hostname.endswith(cur.hostname or ""):
            return strip_tracking(urlunparse((tar.scheme, tar.netloc, tar.path, "", "", "")))
        return None
    except Exception:
        return None


def strip_tracking(url: str) -> str:
    try:
        p = urlparse(url)
        keep = {}
        # LinkedIn often uses currentJobId which we handled above; else drop
        # Drop common UTM/refs
        clean = urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
        return clean
    except Exception:
        return url


def ats_host_of(url: str) -> Optional[str]:
    try:
        h = urlparse(url).hostname or ""
        for known in settings.ats.get("known_hosts", []):
            if h == known or h.endswith("." + known):
                return h
        return None
    except Exception:
        return None
