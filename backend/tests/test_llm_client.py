"""Groq-primary/Gemini-failover client: real calls plus a deliberately
blocked-primary-path test, per Step 4's Definition of Done."""

import httpx
import pytest
from groq import RateLimitError

from app.council import llm_client
from tests.conftest import skip_on_rate_limit


def _rate_limit_error(retry_after: str | None = None) -> RateLimitError:
    headers = {"retry-after": retry_after} if retry_after else {}
    response = httpx.Response(
        429, headers=headers, request=httpx.Request("POST", "http://test.invalid")
    )
    return RateLimitError("rate limited", response=response, body=None)


def test_groq_call_succeeds_for_real():
    with skip_on_rate_limit():
        response = llm_client.chat_completion(
            "You are a terse assistant.", "Reply with exactly: pong"
        )
    assert response.backend == "groq"
    assert "pong" in response.text.lower()


def test_gemini_failover_when_groq_path_is_blocked(monkeypatch):
    """Deliberately block the Groq path and confirm the call still
    resolves via Gemini, per CORRIX_BUILD_PLAN.md Step 4's own DoD item,
    stated for the Council graph but exercised here at the client level."""

    def _broken_groq(*args, **kwargs):
        raise RuntimeError("simulated Groq outage")

    monkeypatch.setattr(llm_client, "_call_groq", _broken_groq)
    with skip_on_rate_limit():
        response = llm_client.chat_completion(
            "You are a terse assistant.", "Reply with exactly: pong"
        )
    assert response.backend == "gemini"
    assert "pong" in response.text.lower()


def test_both_backends_failing_raises(monkeypatch):
    def _broken(*args, **kwargs):
        raise RuntimeError("simulated outage")

    monkeypatch.setattr(llm_client, "_call_groq", _broken)
    monkeypatch.setattr(llm_client, "_call_gemini", _broken)
    with pytest.raises(RuntimeError):
        llm_client.chat_completion("system", "user")


def test_groq_retries_are_bounded_then_falls_back_to_gemini(monkeypatch):
    """A persistent 429 must not stall the call waiting on Groq's own
    long retry-after honoring: at most `groq_max_consecutive_429s`
    attempts, a short sleep between them, then straight to Gemini."""
    call_count = 0
    sleep_calls: list[float] = []

    class _FakeCompletions:
        def create(self, **kwargs):
            nonlocal call_count
            call_count += 1
            raise _rate_limit_error(retry_after="0.01")

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeGroqClient:
        def __init__(self, *args, **kwargs):
            self.chat = _FakeChat()

    monkeypatch.setattr(llm_client, "Groq", _FakeGroqClient)
    monkeypatch.setattr(llm_client.time, "sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(llm_client, "_call_gemini", lambda *a, **k: "pong")

    response = llm_client.chat_completion("system", "user")

    assert response.backend == "gemini"
    settings = llm_client.get_settings()
    assert call_count == settings.groq_max_consecutive_429s
    assert len(sleep_calls) == settings.groq_max_consecutive_429s - 1
