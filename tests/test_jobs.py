import httpx
import pytest

from app import jobs

LONG = "Vi söker en kulturproducent som ska arbeta med publika program. " * 8


def test_html_to_text_prefers_main_and_strips_noise():
    html = f"<html><body><nav>Meny</nav><main><h1>Producent</h1><p>{LONG}</p></main><footer>Cookies</footer><script>x()</script></body></html>"
    text = jobs.html_to_text(html)
    assert "Producent" in text and "kulturproducent" in text
    assert "Meny" not in text and "Cookies" not in text and "x()" not in text


def test_json_ld_job_posting_is_used():
    description = "<p>" + LONG + "</p>"
    html = (
        '<html><body><div>' + "x " * 10 + '</div><script type="application/ld+json">'
        '{"@type": "JobPosting", "title": "Museipedagog", "description": ' + __import__("json").dumps(description) + "}"
        "</script></body></html>"
    )
    text = jobs.html_to_text(html)
    assert text.startswith("Museipedagog") and "kulturproducent" in text


def test_rejects_non_http_urls():
    with pytest.raises(jobs.JobFetchError):
        jobs.fetch_job_text("file:///etc/passwd")
    with pytest.raises(jobs.JobFetchError):
        jobs.fetch_job_text("not a url")


def test_fetch_success(monkeypatch):
    html = f"<html><body><main><p>{LONG}</p></main></body></html>"
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(200, text=html, request=httpx.Request("GET", a[0])))
    assert "kulturproducent" in jobs.fetch_job_text("https://example.com/job")


def test_fetch_too_little_text(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(200, text="<html><body>Loading</body></html>", request=httpx.Request("GET", a[0])))
    with pytest.raises(jobs.JobFetchError, match="Paste the posting text"):
        jobs.fetch_job_text("https://example.com/job")


def test_fetch_http_error(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "get", boom)
    with pytest.raises(jobs.JobFetchError, match="Could not fetch"):
        jobs.fetch_job_text("https://example.com/job")
