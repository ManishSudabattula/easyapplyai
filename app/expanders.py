from __future__ import annotations

import time
from typing import Dict, List

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


def scroll_lazy(page, scrolls: int = 4):
    for _ in range(max(scrolls, 1)):
        page.keyboard.press("PageDown")
        time.sleep(0.1)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")


def _text_len(el) -> int:
    try:
        return len(el.inner_text() or "")
    except Exception:
        try:
            return len(el.text_content() or "")
        except Exception:
            return 0


def stabilize_textlen(el, timeout_ms: int) -> None:
    deadline = time.time() + (timeout_ms / 1000.0)
    last = _text_len(el)
    while time.time() < deadline:
        time.sleep(0.1)
        cur = _text_len(el)
        if cur == last:
            return
        last = cur


def _find_desc_root(page, selectors: List[str]):
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                return el
        except Exception:
            continue
    return None


def _try_clicks_within(root, page, selectors: List[str], max_clicks: int, stabilize_ms: int, selectors_tried: List[str]) -> int:
    clicks = 0
    for sel in selectors:
        if clicks >= max_clicks:
            break
        try:
            el = root.query_selector(sel) or page.query_selector(sel)
            if el:
                selectors_tried.append(sel)
                el.scroll_into_view_if_needed()
                el.click()
                stabilize_textlen(root, stabilize_ms)
                clicks += 1
        except Exception:
            continue
    if clicks < max_clicks:
        # Generic role-based button
        try:
            btns = page.get_by_role("button", name=r"see more|show more|read more", exact=False)
            try:
                b = btns.nth(0)
                b.scroll_into_view_if_needed()
                b.click()
                stabilize_textlen(root, stabilize_ms)
                clicks += 1
            except Exception:
                pass
        except Exception:
            pass
    return clicks


def _unclamp_css(root) -> None:
    try:
        root.evaluate(
            "(node) => {\n"
            "  const isClamped = (el) => {\n"
            "    const classes = el.className || '';\n"
            "    return /clamp|show-more|line-clamp/i.test(classes);\n"
            "  };\n"
            "  const stack = [node];\n"
            "  while (stack.length) {\n"
            "    const el = stack.pop();\n"
            "    if (!el) continue;\n"
            "    if (isClamped(el)) {\n"
            "      el.style.maxHeight = 'none';\n"
            "      el.style.webkitLineClamp = 'unset';\n"
            "      el.className = String(el.className).replace(/show-more-less-html__markup--clamp/g, '');\n"
            "    }\n"
            "    const children = el.children || [];\n"
            "    for (let i=0;i<children.length;i++) stack.push(children[i]);\n"
            "  }\n"
            "}"
        )
    except Exception:
        pass


def expand_description(page, platform: str, desc_root_selectors: List[str], settings) -> Dict:
    expand_cfg = getattr(settings, 'expand', {}) or {}
    selectors_map = expand_cfg.get('selectors', {})
    max_clicks = int(expand_cfg.get('max_clicks', 4))
    stabilize_ms = int(expand_cfg.get('stabilize_ms', 700))
    min_delta_chars = int(expand_cfg.get('min_delta_chars', 200))

    root = _find_desc_root(page, desc_root_selectors)
    if not root:
        return {"expanded": False, "attempts": 0, "before_len": 0, "after_len": 0, "selectors_tried": []}

    before_len = _text_len(root)
    selectors_tried: List[str] = []
    attempts = 0

    # Click loop
    plat_selectors = selectors_map.get(platform, []) + selectors_map.get('generic', [])
    attempts += _try_clicks_within(root, page, plat_selectors, max_clicks, stabilize_ms, selectors_tried)

    after_len = _text_len(root)
    if after_len - before_len < min_delta_chars:
        # try css unclamp fallback
        _unclamp_css(root)
        stabilize_textlen(root, stabilize_ms)
        after_len = _text_len(root)

    return {
        "expanded": after_len > before_len,
        "attempts": attempts,
        "before_len": before_len,
        "after_len": after_len,
        "selectors_tried": selectors_tried,
        "css_unclamp": after_len > before_len and attempts == 0,
    }
