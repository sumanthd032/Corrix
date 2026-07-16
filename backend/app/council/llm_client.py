"""Groq-primary, Gemini-failover inference client, per CORRIX_PROJECT.md
§7.1: Groq is the latency-critical primary path; Gemini is a genuine
fallback for when Groq's path fails or its rate limit is hit mid-demo —
never a 50/50 load-balanced co-primary, since Gemini's free tier is
materially tighter.

`_call_groq` and `_call_gemini` are separated from `chat_completion` so a
test can monkeypatch `_call_groq` to raise, deliberately simulating a
blocked primary path (CORRIX_BUILD_PLAN.md Step 4's own DoD item) without
needing to actually exhaust Groq's real rate limit.
"""

import logging
from dataclasses import dataclass
from typing import Literal

from google import genai
from groq import Groq

from app.config import get_settings

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.1-8b-instant"
GEMINI_MODEL = "gemini-flash-latest"

Backend = Literal["groq", "gemini"]


@dataclass
class LLMResponse:
    text: str
    backend: Backend


def _call_groq(system_prompt: str, user_prompt: str, max_tokens: int) -> str:
    settings = get_settings()
    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    return response.choices[0].message.content


def _call_gemini(system_prompt: str, user_prompt: str, max_tokens: int) -> str:
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=f"{system_prompt}\n\n{user_prompt}",
    )
    return response.text


def chat_completion(
    system_prompt: str, user_prompt: str, max_tokens: int = 300
) -> LLMResponse:
    """Try Groq first; on any failure, fall back to Gemini once. If both
    fail, the second exception propagates — there is no third path."""
    try:
        text = _call_groq(system_prompt, user_prompt, max_tokens)
        return LLMResponse(text=text, backend="groq")
    except Exception as groq_error:
        logger.warning("Groq call failed, falling back to Gemini: %s", groq_error)
        text = _call_gemini(system_prompt, user_prompt, max_tokens)
        return LLMResponse(text=text, backend="gemini")
