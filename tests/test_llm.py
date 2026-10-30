import json

import pytest

from app import llm
from app.llm import LLMError

VALID_DRAFT = {
    "analysis": {
        "title": "Producent",
        "employer": "Exempelmuseet",
        "language": "sv",
        "requirements": [{"text": "Erfarenhet av produktion", "evidence": "Producerade 12 utställningar", "source": "cv.pdf"}],
        "keywords": ["publik"],
    },
    "cv": {
        "language": "sv",
        "summary": "Producent.",
        "experience": [{"role": "Producent", "employer": "Exempelmuseet", "bullets": [{"text": "Producerade 12 utställningar", "source": "cv.pdf"}]}],
    },
}


def test_draft_cv_retries_when_cv_is_incomplete():
    incomplete = {**VALID_DRAFT, "cv": {"language": "sv", "summary": "Har femdubblat...", "experience": []}}
    replies = iter([json.dumps(incomplete), json.dumps(VALID_DRAFT)])
    calls = []

    def complete(system, user):
        calls.append(user)
        return next(replies)

    assert llm.draft_cv("job", "corpus", complete=complete).cv.experience
    assert len(calls) == 2 and "no experience or projects" in calls[1]


def test_extract_json_ignores_surrounding_prose_and_fences():
    assert llm.extract_json('Here you go:\n```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_without_object():
    with pytest.raises(ValueError):
        llm.extract_json("no json here")


def test_draft_cv_parses_valid_response():
    draft = llm.draft_cv("job", "corpus", complete=lambda s, u: json.dumps(VALID_DRAFT))
    assert draft.cv.summary == "Producent." and draft.analysis.requirements[0].source == "cv.pdf"


def test_draft_cv_sends_job_and_corpus():
    seen = {}

    def complete(system, user):
        seen["system"], seen["user"] = system, user
        return json.dumps(VALID_DRAFT)

    llm.draft_cv("THE JOB", "THE CORPUS", complete=complete)
    assert "THE JOB" in seen["user"] and "THE CORPUS" in seen["user"]
    assert "ONLY facts" in seen["system"]


def test_draft_cv_retries_once_on_malformed_json():
    replies = iter(["not json", json.dumps(VALID_DRAFT)])
    calls = []

    def complete(system, user):
        calls.append(user)
        return next(replies)

    assert llm.draft_cv("job", "corpus", complete=complete).cv.summary == "Producent."
    assert len(calls) == 2 and "could not be parsed" in calls[1]


def test_draft_cv_fails_after_second_bad_response():
    with pytest.raises(LLMError, match="invalid JSON twice"):
        llm.draft_cv("job", "corpus", complete=lambda s, u: "still not json")


def test_draft_cv_requires_sources():
    with pytest.raises(LLMError, match="at least one source"):
        llm.draft_cv("job", "  ", complete=lambda s, u: "")


def test_regenerate_section_returns_validated_value(sample_cv):
    reply = json.dumps({"summary": "Kortare sammanfattning."})
    value = llm.regenerate_section("job", "corpus", sample_cv, "summary", "kortare", complete=lambda s, u: reply)
    assert value == "Kortare sammanfattning."


def test_regenerate_structured_section(sample_cv):
    reply = json.dumps({"experience": [{"role": "Producent", "bullets": [{"text": "X", "source": "cv.pdf"}]}]})
    value = llm.regenerate_section("job", "corpus", sample_cv, "experience", "", complete=lambda s, u: reply)
    assert value[0]["role"] == "Producent" and value[0]["bullets"][0]["text"] == "X"


def test_regenerate_unknown_section(sample_cv):
    with pytest.raises(LLMError, match="Unknown section"):
        llm.regenerate_section("job", "corpus", sample_cv, "contact", "", complete=lambda s, u: "")
