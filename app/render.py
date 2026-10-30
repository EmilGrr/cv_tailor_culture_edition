import subprocess
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .config import get_settings
from .models import CV, HIDEABLE_SECTIONS

TEMPLATE_DIR = Path(__file__).parent / "templates"

TEMPLATES = {
    "classic": "Classic - serif, centred header",
    "fun": "Fun - colourful and playful",
    "compact": "Compact - dense, for longer histories",
}

LABELS = {
    "sv": {
        "summary": "Sammanfattning",
        "core_skills": "Kompetenser",
        "experience": "Erfarenhet",
        "projects": "Uppdrag och projekt",
        "education": "Utbildning",
        "languages": "Språk",
        "digital_skills": "Digitala kunskaper",
        "volunteer": "Ideellt engagemang",
        "references": "Referenser",
        "present": "nu",
        "default_references": "Referenser lämnas på begäran",
    },
    "en": {
        "summary": "Summary",
        "core_skills": "Key skills",
        "experience": "Experience",
        "projects": "Projects and assignments",
        "education": "Education",
        "languages": "Languages",
        "digital_skills": "Digital skills",
        "volunteer": "Volunteering",
        "references": "References",
        "present": "present",
        "default_references": "References available on request",
    },
}

_TEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


class RenderError(RuntimeError):
    pass


def latex_escape(text: str) -> str:
    text = " ".join(text.split())
    return "".join(_TEX_ESCAPES.get(ch, ch) for ch in text)


def _escape_tree(value):
    if isinstance(value, str):
        return latex_escape(value)
    if isinstance(value, list):
        return [_escape_tree(v) for v in value]
    if isinstance(value, dict):
        return {k: _escape_tree(v) for k, v in value.items()}
    return value


def _join(parts, sep=", "):
    return sep.join(p for p in parts if p)


def _period(start: str, end: str, present: str) -> str:
    if start and not end:
        return f"{start} – {present}"
    return _join([start, end], " – ")


def build_context(cv: CV) -> dict:
    labels = LABELS[cv.language]
    c = _escape_tree(cv.model_dump())
    for e in c["experience"]:
        e["period"] = _period(e["start"], e["end"], labels["present"])
        e["employer_line"] = _join([e["employer"], e["place"]])
    for p in c["projects"]:
        p["meta"] = _join([p["role"], p["partner"]])
    for edu in c["education"]:
        edu["line"] = edu["institution"]
    contact = c["contact"]
    return {
        "L": labels,
        "lang": {"sv": "swedish", "en": "english"}[cv.language],
        "c": c,
        "show": {key: key not in cv.hidden_sections for key in HIDEABLE_SECTIONS},
        "contact_line": _join(
            [contact["city"], contact["email"], contact["phone"], *contact["links"]], " · "
        ),
        "skills_line": _join(c["core_skills"]),
        "digital_line": _join(c["digital_skills"]),
        "languages_line": _join(
            [f"{x['name']} ({x['level']})" if x["level"] else x["name"] for x in c["languages"] if x["name"]],
            "; ",
        ),
        "references": c["references"] or latex_escape(labels["default_references"]),
    }


def render_tex(cv: CV, template: str) -> str:
    if template not in TEMPLATES:
        raise RenderError(f"Unknown template '{template}'.")
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        block_start_string="<%",
        block_end_string="%>",
        variable_start_string="<<",
        variable_end_string=">>",
        comment_start_string="<#",
        comment_end_string="#>",
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
    )
    return env.get_template(f"{template}.tex.j2").render(**build_context(cv))


def compile_pdf(tex: str, timeout: int = 300) -> bytes:
    tectonic = get_settings().tectonic
    if not tectonic:
        raise RenderError("Tectonic was not found. Install it or set TECTONIC_PATH in .env.")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "cv.tex").write_text(tex, encoding="utf-8")
        try:
            result = subprocess.run(
                [tectonic, "cv.tex"],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RenderError("LaTeX compilation timed out. The first run downloads packages; try again.") from exc
        pdf = tmp_path / "cv.pdf"
        if result.returncode != 0 or not pdf.exists():
            raise RenderError(f"LaTeX compilation failed:\n{result.stderr or result.stdout}")
        return pdf.read_bytes()


def render_pdf(cv: CV, template: str) -> bytes:
    return compile_pdf(render_tex(cv, template))
