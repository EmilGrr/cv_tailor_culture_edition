import pytest

from app import llm
from app.llm import LLMError


def test_bedrock_requires_explicit_credentials(monkeypatch):
    for name in ("AWS_BEARER_TOKEN_BEDROCK", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(LLMError, match="No AWS credentials"):
        llm.bedrock_complete("system", "user")


def test_bedrock_sends_converse_request(monkeypatch):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "token")
    seen = {}

    class FakeClient:
        def converse(self, **kwargs):
            seen.update(kwargs)
            return {"output": {"message": {"content": [{"text": '{"ok": '}, {"text": "true}"}]}}}

    monkeypatch.setattr("app.llm.boto3.client", lambda *a, **k: FakeClient())
    assert llm.bedrock_complete("SYS", "USER") == '{"ok": true}'
    assert seen["modelId"] == "eu.anthropic.claude-sonnet-5-5"
    assert seen["system"] == [{"text": "SYS"}] and seen["messages"][0]["content"] == [{"text": "USER"}]
