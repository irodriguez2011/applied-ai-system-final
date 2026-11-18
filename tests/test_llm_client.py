"""LLM client tests. None of these call the real API or read .env."""

import pytest

from src import llm_client
from src.llm_client import GeminiClient, LLMError, MockClient


# --- MockClient ---------------------------------------------------------


def test_mock_replays_replies_in_order_and_records_prompts():
    client = MockClient(['{"tool": "ask_user"}', '{"final": [1, 2]}'])
    assert client.complete("sys", "first") == '{"tool": "ask_user"}'
    assert client.complete("sys", "second") == '{"final": [1, 2]}'
    assert client.calls == [("sys", "first"), ("sys", "second")]


def test_mock_raises_when_out_of_replies():
    client = MockClient([])
    with pytest.raises(LLMError, match="no replies left"):
        client.complete("sys", "hello")


# --- GeminiClient (no network) ------------------------------------------


def test_missing_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LLMError, match="GEMINI_API_KEY is not set"):
        GeminiClient()


def test_placeholder_key_is_treated_as_missing():
    with pytest.raises(LLMError, match="not set"):
        GeminiClient(api_key="your_api_key_here")


class _FakeModels:
    """Stands in for client.models so no request leaves the machine."""

    def __init__(self, text=None, error=None):
        self.text, self.error, self.last_call = text, error, None

    def generate_content(self, **kwargs):
        self.last_call = kwargs
        if self.error:
            raise self.error
        return type("Response", (), {"text": self.text})()


def _client_with(models):
    client = GeminiClient(api_key="fake-key-123")
    client.client = type("FakeGenai", (), {"models": models})()
    return client


def test_gemini_sends_system_prompt_and_asks_for_json():
    models = _FakeModels(text='{"ok": true}')
    assert _client_with(models).complete("be a DJ", "chill songs") == '{"ok": true}'
    config = models.last_call["config"]
    assert config.system_instruction == "be a DJ"
    assert config.response_mime_type == "application/json"
    assert models.last_call["contents"] == "chill songs"


def test_api_failure_becomes_llm_error_without_the_key():
    models = _FakeModels(error=RuntimeError("401 bad key fake-key-123"))
    with pytest.raises(LLMError) as info:
        _client_with(models).complete("sys", "user")
    assert "fake-key-123" not in str(info.value)
    assert "[hidden]" in str(info.value)


def test_empty_reply_becomes_llm_error():
    with pytest.raises(LLMError, match="empty reply"):
        _client_with(_FakeModels(text=None)).complete("sys", "user")


def test_check_connection_reports_failure_instead_of_crashing(monkeypatch):
    def no_client():
        raise LLMError("GEMINI_API_KEY is not set")

    monkeypatch.setattr(llm_client, "load_gemini_client", no_client)
    works, reason = llm_client.check_connection()
    assert not works and "not set" in reason
