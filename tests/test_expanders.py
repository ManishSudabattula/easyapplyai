from __future__ import annotations

from pathlib import Path

from app.settings import settings
from app.browser import open_persistent, set_fixture_html
from app.expanders import expand_description
from app.extractors import description_roots_for


COLLAPSED_HTML = """
<!doctype html>
<html>
<body>
  <div id="job-details">
    <div class="show-more-less-html__markup show-more-less-html__markup--clamp">
      <p>Short text...</p>
      <p>More content that is initially hidden More content that is initially hidden More content that is initially hidden.</p>
    </div>
    <button class="show-more-less-html__button--more" onclick="document.querySelector('.show-more-less-html__markup').classList.remove('show-more-less-html__markup--clamp')">See more</button>
  </div>
</body>
</html>
"""


def test_expander_click_and_unclamp(tmp_path: Path):
    # Use a headless page with content
    pw = browser = context = page = None
    try:
        pw, browser, context, page = open_persistent(headless=True, storage_state=None)
        set_fixture_html(page, COLLAPSED_HTML)
        # Run expander for linkedin roots
        roots = description_roots_for("linkedin")
        res = expand_description(page, "linkedin", roots, settings)
        assert res["after_len"] >= res["before_len"]
        assert res["expanded"] is True
    finally:
        try:
            if page:
                page.close()
            if context:
                context.close()
            if browser:
                browser.close()
            if pw:
                pw.stop()
        except Exception:
            pass
