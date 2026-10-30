import json
from collections.abc import Callable

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from pydantic import TypeAdapter, ValidationError

from . import prompts
from .config import fake_llm_enabled, get_settings, has_aws_credentials
from .models import CV, REGENERABLE_SECTIONS, Draft

# A completion function takes (system prompt, user message) and returns the model's text.
Complete = Callable[[str, str], str]


class LLMError(RuntimeError):
    pass


def bedrock_complete(system: str, user: str) -> str:
    if fake_llm_enabled():
        from . import fake_llm

        return fake_llm.complete(system, user)
    if not has_aws_credentials():
        raise LLMError("No AWS credentials found. Add them to the .env file (see .env.example).")
    settings = get_settings()
    client = boto3.client(
        "bedrock-runtime",
        region_name=settings.region,
        config=Config(read_timeout=300, retries={"max_attempts": 3, "mode": "standard"}),
    )
    try:
        response = client.converse(
            modelId=settings.model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": 16000},
        )
    except NoCredentialsError as exc:
        raise LLMError("No AWS credentials found. Add them to the .env file.") from exc
    except ClientError as exc:
        error = exc.response.get("Error", {})
        code, message = error.get("Code", "ClientError"), error.get("Message", str(exc))
        raise LLMError(f"Bedrock error ({code}): {message}") from exc
    except BotoCoreError as exc:
        raise LLMError(f"Could not reach Bedrock: {exc}") from exc
    blocks = response["output"]["message"]["content"]
    return "".join(block.get("text", "") for block in blocks)


def extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("The response contained no JSON object.")
    return json.loads(text[start : end + 1])


def _ask_for_json(complete: Complete, system: str, user: str, parse: Callable[[dict], object]):
    raw = complete(system, user)
    try:
        return parse(extract_json(raw))
    except (ValueError, ValidationError) as first_error:
        retry_user = (
            f"{user}\n\nYour previous answer could not be parsed ({first_error}). "
            "Return ONLY the corrected JSON object."
        )
        raw_retry = complete(system, retry_user)
        try:
            return parse(extract_json(raw_retry))
        except (ValueError, ValidationError) as second_error:
            raise LLMError(f"The model returned invalid JSON twice: {second_error}\n\n{raw_retry}") from second_error


def _validated_draft(data: dict) -> Draft:
    draft = Draft.model_validate(data)
    cv = draft.cv
    if not (cv.experience or cv.projects):
        raise ValueError("The CV has no experience or projects. Write the complete CV.")
    if not cv.summary.strip() or "..." in cv.summary or "…" in cv.summary:
        raise ValueError("The summary is missing or unfinished. Write a complete summary.")
    return draft


def draft_cv(job_text: str, corpus: str, complete: Complete | None = None) -> Draft:
    if not corpus.strip():
        raise LLMError("Add at least one source document or note before drafting.")
    return _ask_for_json(
        complete or bedrock_complete,
        prompts.SYSTEM_PROMPT,
        prompts.draft_user_message(job_text, corpus),
        _validated_draft,
    )


def regenerate_section(
    job_text: str,
    corpus: str,
    cv: CV,
    section: str,
    instruction: str,
    complete: Complete | None = None,
):
    if section not in REGENERABLE_SECTIONS:
        raise LLMError(f"Unknown section '{section}'.")
    field_type = CV.model_fields[section].annotation
    adapter = TypeAdapter(field_type)

    def parse(data: dict):
        if section not in data:
            raise ValueError(f'The JSON object is missing the key "{section}".')
        return adapter.validate_python(data[section])

    value = _ask_for_json(
        complete or bedrock_complete,
        prompts.SECTION_SYSTEM_PROMPT,
        prompts.section_user_message(job_text, corpus, cv.model_dump_json(), section, instruction),
        parse,
    )
    return adapter.dump_python(value, mode="json")
