import io

import pytest
from fastapi.testclient import TestClient

from app import llm
from app.main import app
from app.models import Draft

client = TestClient(app)

DRAFT = Draft.model_validate(
    {
        "analysis": {"title": "Producent", "employer": "Exempelmuseet", "language": "sv", "requirements": [], "keywords": []},
        "cv": {"language": "sv", "contact": {"name": "Anna Exempel"}, "summary": "Producent."},
    }
)


def _add_note():
    return client.post("/api/sources/note", json={"name": "Notes", "text": "Jag har producerat utställningar."})


def test_status_lists_templates():
    body = client.get("/api/status").json()
    assert {t["id"] for t in body["templates"]} == {"classic", "fun", "compact"}
    assert body["model_id"] == "eu.anthropic.claude-sonnet-5-5"


def test_upload_reports_added_and_errors():
    files = [
        ("files", ("cv.txt", io.BytesIO("Hej".encode()), "text/plain")),
        ("files", ("bad.exe", io.BytesIO(b"x"), "application/octet-stream")),
    ]
    body = client.post("/api/sources/upload", files=files).json()
    assert len(body["added"]) == 1 and body["errors"][0]["name"] == "bad.exe"
    assert client.get("/api/sources").json()[0]["name"] == "cv.txt"


def test_empty_note_rejected():
    assert client.post("/api/sources/note", json={"name": "x", "text": "  "}).status_code == 422


def test_source_update_and_delete():
    sid = _add_note().json()["id"]
    assert client.put(f"/api/sources/{sid}", json={"name": "New", "text": "changed"}).status_code == 200
    assert client.get(f"/api/sources/{sid}").json()["text"] == "changed"
    assert client.delete(f"/api/sources/{sid}").status_code == 204
    assert client.get(f"/api/sources/{sid}").status_code == 404


def test_fetch_job_error_is_422():
    assert client.post("/api/job/fetch", json={"url": "ftp://x"}).status_code == 422


def test_draft_edit_and_reload_flow(monkeypatch):
    _add_note()
    monkeypatch.setattr(llm, "bedrock_complete", lambda s, u: "unused")
    monkeypatch.setattr(llm, "draft_cv", lambda job, corpus, complete=None: DRAFT)
    created = client.post("/api/draft", json={"job_text": "Vi söker en producent. " * 5}).json()
    assert created["title"] == "Producent - Exempelmuseet" and created["template"] == "classic"

    cv = created["cv"]
    cv["summary"] = "Redigerad."
    saved = client.put(f"/api/applications/{created['id']}", json={"cv": cv, "template": "fun"}).json()
    assert saved["cv"]["summary"] == "Redigerad." and saved["template"] == "fun"
    assert client.get("/api/applications").json()[0]["id"] == created["id"]
    assert client.get(f"/api/applications/{created['id']}").json()["template"] == "fun"
    assert client.delete(f"/api/applications/{created['id']}").status_code == 204


def test_draft_without_sources_gives_502():
    response = client.post("/api/draft", json={"job_text": "Vi söker en producent. " * 5})
    assert response.status_code == 502 and "source" in response.json()["detail"]


def test_draft_rejects_short_job_text():
    assert client.post("/api/draft", json={"job_text": "hi"}).status_code == 422


def test_regenerate_section(monkeypatch):
    _add_note()
    monkeypatch.setattr(llm, "draft_cv", lambda job, corpus, complete=None: DRAFT)
    created = client.post("/api/draft", json={"job_text": "Vi söker en producent. " * 5}).json()
    monkeypatch.setattr(llm, "bedrock_complete", lambda s, u: '{"summary": "Ny text."}')
    response = client.post(
        f"/api/applications/{created['id']}/regenerate",
        json={"cv": created["cv"], "section": "summary", "instruction": "kortare"},
    )
    assert response.json() == {"section": "summary", "value": "Ny text."}


def test_regenerate_unknown_section_is_502():
    created = __import__("app.storage", fromlist=["x"]).create_application({"title": "t", "job_text": "j", "cv": {}})
    response = client.post(f"/api/applications/{created['id']}/regenerate", json={"cv": {}, "section": "contact"})
    assert response.status_code == 502


def test_unknown_template_rejected_on_save(monkeypatch):
    created = __import__("app.storage", fromlist=["x"]).create_application({"title": "t", "job_text": "j"})
    assert client.put(f"/api/applications/{created['id']}", json={"cv": {}, "template": "zzz"}).status_code == 422


def test_application_saved_with_the_old_modern_template_opens_as_fun():
    from app import storage

    created = storage.create_application({"title": "t", "template": "modern"})
    assert client.get(f"/api/applications/{created['id']}").json()["template"] == "fun"


@pytest.mark.skipif(__import__("app.config", fromlist=["x"]).get_settings().tectonic is None, reason="tectonic missing")
def test_render_endpoint_returns_pdf(sample_cv):
    response = client.post("/api/render", json={"cv": sample_cv.model_dump(), "template": "classic"})
    assert response.status_code == 200 and response.content.startswith(b"%PDF")


def test_render_unknown_template_is_422(sample_cv):
    assert client.post("/api/render", json={"cv": sample_cv.model_dump(), "template": "zzz"}).status_code == 422
