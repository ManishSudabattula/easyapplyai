from __future__ import annotations

import os
import json
from typing import Dict, List

import orjson
from pydantic import BaseModel

from .hashing import sha256_bytes
from .settings import settings


class _LLMConfig(BaseModel):
    provider: str
    model_primary: str
    model_fallbacks: List[str] = []
    temperature: float = 0.1
    top_p: float = 0.95
    max_tokens: int = 1200
    request_timeout_s: int = 18
    max_retries: int = 1
    enabled: bool = True
    redact_logs: bool = True


def _openrouter_headers() -> Dict[str, str]:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("Missing OPENROUTER_API_KEY in environment")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _post_openrouter(model: str, messages: List[Dict], **kwargs) -> Dict:
    import requests

    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": kwargs.get("temperature", 0.1),
        "top_p": kwargs.get("top_p", 0.95),
        "max_tokens": kwargs.get("max_tokens", 1200),
        "response_format": {"type": "json_object"},
    }
    timeout = kwargs.get("timeout", 18)
    resp = requests.post(url, headers=_openrouter_headers(), data=json.dumps(payload), timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _parse_json_object(s: str) -> Dict[str, str]:
    try:
        obj = json.loads(s)
        if not isinstance(obj, dict):
            return {}
        result = {}
        for k in ("title", "company", "location", "description_text"):
            v = obj.get(k, "")
            if isinstance(v, str):
                result[k] = v
            else:
                result[k] = ""
        return result
    except Exception:
        return {}


def infer_fields(missing_keys: List[str], context_text: str, platform: str, page_url: str | None = None) -> Dict[str, str]:
    cfg = _LLMConfig(**settings.llm)
    if not cfg.enabled:
        return {k: "" for k in missing_keys}

    from .prompts import build_infer_prompt

    prompt = build_infer_prompt(missing_keys, platform, page_url or "")
    messages = [
        {"role": "system", "content": "You are a precise information extractor that only outputs strict JSON."},
        {"role": "user", "content": prompt},
        {"role": "user", "content": f"CONTEXT:\n{context_text}"},
    ]

    models = [cfg.model_primary] + list(cfg.model_fallbacks)
    errors: List[str] = []
    for model in models[: 1 + int(cfg.max_retries)]:
        try:
            data = _post_openrouter(
                model,
                messages,
                temperature=cfg.temperature,
                top_p=cfg.top_p,
                max_tokens=cfg.max_tokens,
                timeout=cfg.request_timeout_s,
            )
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = _parse_json_object(content)
            return {k: (parsed.get(k) or "") for k in missing_keys}
        except Exception as e:
            errors.append(f"{type(e).__name__}:{e}")
            continue
    # All failed
    return {k: "" for k in missing_keys}


def redact_hashes(prompt: str, context: str, response: str) -> Dict[str, str]:
    return {
        "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "context_sha256": sha256_bytes(context.encode("utf-8")),
        "response_sha256": sha256_bytes(response.encode("utf-8")),
        "prompt_len": len(prompt),
        "context_len": len(context),
        "response_len": len(response),
    }
