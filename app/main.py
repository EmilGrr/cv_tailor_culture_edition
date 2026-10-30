from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pypdf import PdfReader

from . import ingest, jobs, llm, render, storage
from .config import demo_data_enabled, fake_llm_enabled, get_settings, has_aws_credentials
from .models import CV

app = FastAPI(title="CV Tailor")


class NoteIn(BaseModel):
    name: str
    text: str


class SourceUpdate(BaseModel):
    name: str
    text: str


class FetchIn(BaseModel):
    url: str


class DraftIn(BaseModel):
    job_text: str
    job_url: str = ""


class RegenerateIn(BaseModel):
    cv: CV
    section: str
    instruction: str = ""


class SaveIn(BaseModel):
    cv: CV
    template: str
    title: str = ""


class RenderIn(BaseModel):
    cv: CV
    template: str


def _not_found(exc: KeyError) -> HTTPException:
    return HTTPException(404, f"Not found: {exc.args[0]}")


@app.get("/api/status")
def status():
    settings = get_settings()
    return {
        "aws_credentials": has_aws_credentials(),
        "demo_model": fake_llm_enabled(),
        "demo_data": demo_data_enabled(),
        "model_id": settings.model_id,
        "region": settings.region,
        "tectonic": settings.tectonic is not None,
        "templates": [{"id": k, "label": v} for k, v in render.TEMPLATES.items()],
    }


@app.get("/api/sources")
def list_sources():
    return [
        {"id": s["id"], "name": s["name"], "kind": s["kind"], "chars": len(s["text"])}
        for s in ingest.list_sources()
    ]


@app.get("/api/sources/{source_id}")
def get_source(source_id: str):
    try:
        return ingest.get_source(source_id)
    except KeyError as exc:
        raise _not_found(exc)


@app.post("/api/sources/upload")
async def upload_sources(files: list[UploadFile] = File(...)):
    added, errors = [], []
    for file in files:
        try:
            text = ingest.extract_text(file.filename or "", await file.read())
        except ingest.IngestError as exc:
            errors.append({"name": file.filename, "error": str(exc)})
            continue
        source = ingest.add_source(file.filename or "Untitled", "file", text)
        added.append({"id": source["id"], "name": source["name"], "chars": len(text)})
    return {"added": added, "errors": errors}


@app.post("/api/sources/note")
def add_note(note: NoteIn):
    if not note.text.strip():
        raise HTTPException(422, "The note is empty.")
    source = ingest.add_source(note.name or "Note", "note", note.text.strip())
    return {"id": source["id"], "name": source["name"], "chars": len(source["text"])}


@app.put("/api/sources/{source_id}")
def update_source(source_id: str, body: SourceUpdate):
    try:
        source = ingest.update_source(source_id, body.name, body.text.strip())
    except KeyError as exc:
        raise _not_found(exc)
    return {"id": source["id"], "name": source["name"], "chars": len(source["text"])}


@app.delete("/api/sources/{source_id}", status_code=204)
def delete_source(source_id: str):
    try:
        ingest.delete_source(source_id)
    except KeyError as exc:
        raise _not_found(exc)


@app.post("/api/job/fetch")
def fetch_job(body: FetchIn):
    try:
        return {"text": jobs.fetch_job_text(body.url)}
    except jobs.JobFetchError as exc:
        raise HTTPException(422, str(exc))


@app.post("/api/draft")
def draft(body: DraftIn):
    if len(body.job_text.strip()) < 40:
        raise HTTPException(422, "The job posting text is too short.")
    try:
        result = llm.draft_cv(body.job_text.strip(), ingest.build_corpus())
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc))
    title = " - ".join(p for p in [result.analysis.title, result.analysis.employer] if p) or "Untitled"
    return storage.create_application(
        {
            "title": title,
            "job_text": body.job_text.strip(),
            "job_url": body.job_url,
            "template": "classic",
            **result.model_dump(),
        }
    )


@app.get("/api/applications")
def list_applications():
    return storage.list_applications()


@app.get("/api/applications/{app_id}")
def get_application(app_id: str):
    try:
        return storage.get_application(app_id)
    except KeyError as exc:
        raise _not_found(exc)


@app.put("/api/applications/{app_id}")
def save_application(app_id: str, body: SaveIn):
    if body.template not in render.TEMPLATES:
        raise HTTPException(422, f"Unknown template '{body.template}'.")
    changes = {"cv": body.cv.model_dump(), "template": body.template}
    if body.title:
        changes["title"] = body.title
    try:
        return storage.update_application(app_id, changes)
    except KeyError as exc:
        raise _not_found(exc)


@app.delete("/api/applications/{app_id}", status_code=204)
def delete_application(app_id: str):
    try:
        storage.delete_application(app_id)
    except KeyError as exc:
        raise _not_found(exc)


@app.post("/api/applications/{app_id}/regenerate")
def regenerate(app_id: str, body: RegenerateIn):
    try:
        application = storage.get_application(app_id)
    except KeyError as exc:
        raise _not_found(exc)
    try:
        value = llm.regenerate_section(
            application["job_text"], ingest.build_corpus(), body.cv, body.section, body.instruction
        )
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc))
    return {"section": body.section, "value": value}


@app.post("/api/render")
def render_cv(body: RenderIn):
    try:
        pdf = render.render_pdf(body.cv, body.template)
    except render.RenderError as exc:
        raise HTTPException(422, str(exc))
    pages = len(PdfReader(BytesIO(pdf)).pages)
    return Response(pdf, media_type="application/pdf", headers={"X-Page-Count": str(pages)})


class NoCacheStatic(StaticFiles):
    """Always revalidate, so edits to the frontend show up on reload."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


STATIC = Path(__file__).parent / "static"
app.mount("/", NoCacheStatic(directory=STATIC, html=True), name="static")
