import json
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

MIN_CHARS = 200
USER_AGENT = "Mozilla/5.0 (compatible; cv-tailor/0.1; local tool)"


class JobFetchError(ValueError):
    pass


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _json_ld_description(soup: BeautifulSoup) -> str:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                title = item.get("title", "")
                description = BeautifulSoup(item.get("description", ""), "html.parser").get_text("\n")
                return clean_text(f"{title}\n\n{description}")
    return ""


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    structured = _json_ld_description(soup)
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form", "svg", "iframe"]):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    page_text = clean_text(root.get_text("\n"))
    # Structured job data is usually the cleanest copy of the posting.
    if len(structured) >= MIN_CHARS and len(structured) >= len(page_text) * 0.5:
        return structured
    return page_text


def fetch_job_text(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise JobFetchError("Enter a full http(s) link to the job posting.")
    try:
        response = httpx.get(
            url.strip(),
            headers={"User-Agent": USER_AGENT, "Accept-Language": "sv,en;q=0.8"},
            follow_redirects=True,
            timeout=20,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise JobFetchError(f"Could not fetch the page ({exc}). Paste the posting text instead.") from exc
    text = html_to_text(response.text)
    if len(text) < MIN_CHARS:
        raise JobFetchError(
            "The page had too little readable text (it may need JavaScript or a login). "
            "Paste the posting text instead."
        )
    return text
