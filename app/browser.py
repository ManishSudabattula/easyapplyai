from __future__ import annotations

from pathlib import Path
from typing import Tuple

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

from .settings import settings


def open_page(headless: bool | None = None):
    """Launch Chromium and return (browser, context, page)."""
    if headless is None:
        headless = bool(settings.playwright.get("headless", True))
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    context = browser.new_context()
    # Block selected resource types for speed
    block_types = set(settings.playwright.get("block_resources", []))
    if block_types:
        def _route(route):
            try:
                if route.request.resource_type in block_types:
                    return route.abort()
            except Exception:
                pass
            return route.continue_()
        context.route("**/*", _route)
    page = context.new_page()
    # Apply default timeouts from settings
    nav_timeout = int(settings.playwright.get("nav_timeout_ms", 15000))
    wait_timeout = int(settings.playwright.get("wait_timeout_ms", 15000))
    page.set_default_navigation_timeout(nav_timeout)
    page.set_default_timeout(wait_timeout)
    return pw, browser, context, page


def open_persistent(headless: bool = True, storage_state: dict | None = None):
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    if storage_state:
        context = browser.new_context(storage_state=storage_state)
    else:
        context = browser.new_context()
    page = context.new_page()
    nav_timeout = int(settings.playwright.get("nav_timeout_ms", 15000))
    wait_timeout = int(settings.playwright.get("wait_timeout_ms", 15000))
    page.set_default_navigation_timeout(nav_timeout)
    page.set_default_timeout(wait_timeout)
    return pw, browser, context, page


def export_storage_state(context) -> dict:
    return context.storage_state()


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.3, min=0.3, max=3),
    retry=retry_if_exception_type((PlaywrightTimeoutError, PlaywrightError)),
)
def goto_with_retry(page, url: str, timeout_ms: int | None = None):
    t = timeout_ms or int(settings.playwright.get("nav_timeout_ms", 15000))
    return page.goto(url, timeout=t, wait_until="load")


def set_fixture_html(page, html: str):
    page.set_content(html, wait_until="load")


def dump_html(page, path: Path) -> Path:
    html = page.content()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def screenshot(page, path: Path) -> Path:
    full = bool(settings.playwright.get("screenshot_full_page", True))
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=full)
    return path
