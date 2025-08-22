from __future__ import annotations

from typing import List


def build_infer_prompt(missing_keys: List[str], platform: str, page_url: str) -> str:
    wanted = ", ".join(missing_keys)
    hints = {
        "linkedin": (
            "On LinkedIn job pages, the title is usually in the top card, the company near the organization link, and the location near flavor metadata."
        ),
        "lever": (
            "On Lever job pages, the header contains the title and categories include the location; the site name is the company."
        ),
        "greenhouse": (
            "On Greenhouse job pages, the app-title contains the title, app-location the location; the site name is often the company."
        ),
        "other": (
            "For generic pages, look for the main job title in the first <h1>, company from site name or near the title, and location near labels like 'Location'."
        ),
    }

    schema = (
        "Return a STRICT JSON object: {\"title\": str, \"company\": str, \"location\": str, \"description_text\": str}."
        " If uncertain, use an empty string for that key. Do not invent data."
        " Do not include HTML tags for title/company/location. description_text should be plain text with bullet points preserved as lines."
    )

    return (
        f"Task: Extract ONLY the requested fields: {wanted}. If uncertain, return empty string. Do not invent data.\n"
        f"Platform: {platform}. URL: {page_url}.\n"
        f"Hints: {hints.get(platform, hints['other'])}\n"
        f"{schema}\n"
        f"You will be provided CONTEXT separately."
    )
