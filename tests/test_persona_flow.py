"""End-to-end flow with the sample persona, using the offline demo model and real files."""

import functools
import http.server
import re
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import demo
from app.config import get_settings
from app.ingest import extract_text
from app.main import app
from app.render import TEMPLATES

client = TestClient(app)
PERSONA_FILES = sorted(demo.PERSONA_DIR.iterdir())
needs_tectonic = pytest.mark.skipif(get_settings().tectonic is None, reason="tectonic not installed")

SV_POSTING = (demo.JOBS_DIR / "kulturproducent-sv.txt").read_text(encoding="utf-8")
EN_POSTING = (demo.JOBS_DIR / "producer-en.txt").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def fake_model(monkeypatch):
    monkeypatch.setenv("CV_FAKE_LLM", "1")


@pytest.fixture
def jobs_server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(demo.JOBS_DIR))
    handler.log_message = lambda *args: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def upload(paths=PERSONA_FILES):
    files = [("files", (p.name, p.read_bytes(), "application/octet-stream")) for p in paths]
    return client.post("/api/sources/upload", files=files).json()


def add_note():
    return client.post(
        "/api/sources/note",
        json={"name": "Anteckning", "text": demo.NOTE_FILE.read_text(encoding="utf-8")},
    ).json()


def draft(posting=SV_POSTING):
    response = client.post("/api/draft", json={"job_text": posting})
    assert response.status_code == 200, response.text
    return response.json()


def pdf_text(cv, template="classic") -> str:
    response = client.post("/api/render", json={"cv": cv, "template": template})
    assert response.status_code == 200, response.text
    return " ".join(extract_text("cv.pdf", response.content).split())


def test_every_persona_format_can_be_uploaded():
    result = upload()
    assert result["errors"] == [] and len(result["added"]) == len(PERSONA_FILES) == 4
    texts = {s["name"]: client.get(f"/api/sources/{s['id']}").json()["text"] for s in client.get("/api/sources").json()}
    assert "2,4 Mkr" in texts["CV_Maja_Lindqvist.docx"] and "2011 – 2014 | Kandidatexamen" in texts["CV_Maja_Lindqvist.docx"]
    assert "9 800 åskådare" in " ".join(texts["Personligt_brev_Kulturhuset_Hamnen.pdf"].split())
    assert "## Styrkor" in texts["Om_mig.md"]
    assert "5 200 besökare" in " ".join(texts["Projekt_och_uppdrag.txt"].split())


def test_demo_seed_loads_files_and_note():
    assert demo.seed() == 5
    kinds = sorted(s["kind"] for s in client.get("/api/sources").json())
    assert kinds == ["file"] * 4 + ["note"]


def test_swedish_draft_from_persona_sources():
    upload()
    add_note()
    app_ = draft()
    cv, analysis = app_["cv"], app_["analysis"]
    assert app_["title"] == "Kulturproducent - Stadsmuseet i Nordhamn"
    assert cv["language"] == "sv" and cv["contact"]["name"] == "Maja Lindqvist"

    known = {s["name"] for s in client.get("/api/sources").json()}
    bullets = [b for e in cv["experience"] for b in e["bullets"]]
    assert len(bullets) == 9 and all(b["source"] in known for b in bullets), "every bullet traces to a document"
    assert next(b for b in bullets if "fem projektmedarbetare" in b["text"])["source"] == "Anteckning"
    assert all(p["source"] in known for p in cv["projects"])

    by_text = {r["text"]: r for r in analysis["requirements"]}
    assert by_text["Budgetansvar"]["source"] == "CV_Maja_Lindqvist.docx"
    assert by_text["Erfarenhet av digitala format och VR"]["evidence"] == "", "unsupported requirement is flagged"
    assert cv["gaps_and_questions"] and cv["left_out"]


def test_missing_documents_show_up_as_missing_sources():
    upload([demo.PERSONA_DIR / "Om_mig.md"])
    cv = draft()["cv"]
    sources = {b["text"]: b["source"] for e in cv["experience"] for b in e["bullets"]}
    assert sources["Införde teckenspråkstolkade visningar och lättläst information."] == "Om_mig.md"
    assert sources["Ansvarar för en projektbudget på 2,4 Mkr, inklusive ansökningar om projektmedel."] == ""
    assert sum(1 for s in sources.values() if s == "") >= 6


def test_draft_requires_sources():
    response = client.post("/api/draft", json={"job_text": SV_POSTING})
    assert response.status_code == 502 and "at least one source" in response.json()["detail"]


def test_url_fetch_extracts_posting_and_drops_page_noise(jobs_server):
    text = client.post("/api/job/fetch", json={"url": f"{jobs_server}/kulturproducent.html"}).json()["text"]
    assert text.startswith("Kulturproducent till Stadsmuseet i Nordhamn") and "Meriterande" in text
    for noise in ("Lediga jobb", "cookies", "window.track", "Integritetspolicy"):
        assert noise not in text
    upload()
    assert draft(text)["title"] == "Kulturproducent - Stadsmuseet i Nordhamn"


def test_url_fetch_failures_ask_for_pasted_text(jobs_server):
    js_only = client.post("/api/job/fetch", json={"url": f"{jobs_server}/js-only.html"})
    assert js_only.status_code == 422 and "Paste the posting text" in js_only.json()["detail"]
    missing = client.post("/api/job/fetch", json={"url": f"{jobs_server}/finns-inte.html"})
    assert missing.status_code == 422 and "Paste the posting text" in missing.json()["detail"]


def test_edit_regenerate_and_reload():
    upload()
    app_ = draft()
    cv = app_["cv"]

    regenerated = client.post(
        f"/api/applications/{app_['id']}/regenerate", json={"cv": cv, "section": "summary", "instruction": "kortare"}
    ).json()
    assert regenerated["section"] == "summary" and len(regenerated["value"]) < len(cv["summary"])

    experience = client.post(
        f"/api/applications/{app_['id']}/regenerate", json={"cv": cv, "section": "experience", "instruction": ""}
    ).json()["value"]
    assert experience[0]["employer"] == "Kulturhuset Hamnen" and experience[0]["bullets"][0]["source"]

    cv["summary"] = regenerated["value"]
    cv["experience"][0]["bullets"][0]["text"] = "Egen formulering."
    cv["hidden_sections"] = ["volunteer"]
    saved = client.put(f"/api/applications/{app_['id']}", json={"cv": cv, "template": "fun", "title": "Min ansökan"}).json()
    reloaded = client.get(f"/api/applications/{app_['id']}").json()
    assert reloaded == saved
    assert reloaded["title"] == "Min ansökan" and reloaded["template"] == "fun"
    assert reloaded["cv"]["hidden_sections"] == ["volunteer"] and reloaded["cv"]["volunteer"]


@needs_tectonic
@pytest.mark.parametrize("template", list(TEMPLATES))
def test_pdf_reflects_edits_and_removed_sections(template):
    upload()
    cv = draft()["cv"]
    cv["experience"][0]["bullets"][0]["text"] = "Min egen formulering & mer."
    cv["hidden_sections"] = ["education", "languages", "references"]

    text = pdf_text(cv, template)
    upper = text.upper()
    assert "Maja Lindqvist" in text and "Min egen formulering & mer." in text
    assert all(h in upper for h in ("SAMMANFATTNING", "ERFARENHET", "UPPDRAG OCH PROJEKT"))
    assert not re.search(r"\b(UTBILDNING|SPRÅK|REFERENSER)\b", upper)
    assert "Göteborgs universitet" not in text, "removed section content is not printed"
    assert "Office 365" in text, "no typographic ligatures that would break keyword matching"
    assert not any(ch in text for ch in "\ufb00\ufb01\ufb02\ufb03\ufb04")


@needs_tectonic
@pytest.mark.parametrize("template, full_cv_pages", [("classic", 2), ("fun", 2), ("compact", 1)])
def test_page_count_is_reported_and_removing_a_section_can_fit_one_page(template, full_cv_pages):
    from io import BytesIO

    from pypdf import PdfReader

    upload()
    cv = draft()["cv"]

    def render(cv):
        response = client.post("/api/render", json={"cv": cv, "template": template})
        pages = len(PdfReader(BytesIO(response.content)).pages)
        assert response.headers["X-Page-Count"] == str(pages)
        return pages

    assert render(cv) == full_cv_pages
    cv["hidden_sections"] = ["volunteer", "digital_skills"]
    assert render(cv) == 1


@needs_tectonic
def test_english_posting_gives_english_cv():
    upload()
    cv = draft(EN_POSTING)["cv"]
    assert cv["language"] == "en" and cv["experience"][0]["role"] == "Producer"
    text = pdf_text(cv, "fun")
    upper = text.upper()
    assert all(h in upper for h in ("EXPERIENCE", "EDUCATION", "REFERENCES")) and "References available on request" in text
    assert "2020 – present" in text
