"""Groq-primary/Gemini-failover client: real calls plus a deliberately
blocked-primary-path test, per Step 4's Definition of Done."""

import pytest

from app.council import llm_client
from tests.conftest import skip_on_rate_limit


def test_groq_call_succeeds_for_real():
    with skip_on_rate_limit():
        response = llm_client.chat_completion(
            "You are a terse assistant.", "Reply with exactly: pong"
        )
    assert response.backend == "groq"
    assert "pong" in response.text.lower()


def test_gemini_failover_when_groq_path_is_blocked(monkeypatch):
    """Deliberately block the Groq path and confirm the call still
    resolves via Gemini — CORRIX_BUILD_PLAN.md Step 4's own DoD item,
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
