import shutil

import pytest

from app.config import get_settings
from app.render import TEMPLATES, RenderError, compile_pdf, latex_escape, render_pdf, render_tex


def test_escape_special_characters():
    assert latex_escape(r"a & b % c $ d # e _ f { g } h ~ i ^ j \ k") == (
        r"a \& b \% c \$ d \# e \_ f \{ g \} h \textasciitilde{} i \textasciicircum{} j \textbackslash{} k"
    )


def test_escape_collapses_newlines():
    assert latex_escape("one\ntwo\n\nthree") == "one two three"


def test_render_tex_escapes_user_text(sample_cv):
    tex = render_tex(sample_cv, "classic")
    assert r"publika program \& samverkan" in tex
    assert r"100\% fokus på publik\_" in tex
    assert r"\$ och \#hashtag \{test\}" in tex
    assert "Producent" in tex and "2020 – nu" in tex


def test_render_tex_swedish_labels_and_default_references(sample_cv):
    tex = render_tex(sample_cv, "fun")
    assert "Sammanfattning" in tex and "Erfarenhet" in tex
    assert "Referenser lämnas på begäran" in tex


def test_render_tex_english_labels(sample_cv):
    sample_cv.language = "en"
    tex = render_tex(sample_cv, "compact")
    assert "Experience" in tex and "References available on request" in tex
    assert "2020 – present" in tex


def test_empty_sections_are_omitted(sample_cv):
    sample_cv.projects = []
    sample_cv.volunteer = []
    tex = render_tex(sample_cv, "classic")
    assert "Uppdrag och projekt" not in tex and "Ideellt engagemang" not in tex


def test_hidden_sections_are_omitted_but_data_is_kept(sample_cv):
    sample_cv.hidden_sections = ["summary", "experience", "references", "languages"]
    tex = render_tex(sample_cv, "classic")
    for heading in ("Sammanfattning", "Erfarenhet", "Referenser", "Språk"):
        assert f"\\cvsection{{{heading}}}" not in tex
    assert "Utbildning" in tex and "Uppdrag och projekt" in tex
    assert sample_cv.experience and sample_cv.summary


def test_references_shown_by_default(sample_cv):
    assert "\\cvsection{Referenser}" in render_tex(sample_cv, "compact")


def test_document_language_follows_cv_language(sample_cv):
    assert r"\setmainlanguage{swedish}" in render_tex(sample_cv, "classic")
    sample_cv.language = "en"
    assert r"\setmainlanguage{english}" in render_tex(sample_cv, "fun")


def test_unknown_template_rejected(sample_cv):
    with pytest.raises(RenderError):
        render_tex(sample_cv, "nope")


def test_missing_tectonic_gives_clear_error(monkeypatch):
    monkeypatch.setenv("TECTONIC_PATH", "")
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setattr("app.config.ROOT", __import__("pathlib").Path("Z:/does-not-exist"))
    with pytest.raises(RenderError, match="Tectonic was not found"):
        compile_pdf("x")


needs_tectonic = pytest.mark.skipif(get_settings().tectonic is None, reason="tectonic not installed")


@needs_tectonic
@pytest.mark.parametrize("template", list(TEMPLATES))
def test_each_template_compiles_to_pdf(sample_cv, template):
    pdf = render_pdf(sample_cv, template)
    assert pdf.startswith(b"%PDF") and len(pdf) > 5000


@needs_tectonic
def test_pdf_text_is_selectable_with_swedish_characters(sample_cv):
    from app.ingest import extract_text

    text = extract_text("cv.pdf", render_pdf(sample_cv, "classic"))
    assert "Göteborg" in text and "Kulturförvaltningen" in text and "Referenser lämnas på begäran" in text
