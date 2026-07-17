"""Groq-primary, Gemini-failover inference client, per CORRIX_PROJECT.md
§7.1: Groq is the latency-critical primary path; Gemini is a genuine
fallback for when Groq's path fails or its rate limit is hit mid-demo;
never a 50/50 load-balanced co-primary, since Gemini's free tier is
materially tighter.

`_call_groq` and `_call_gemini` are separated from `chat_completion` so a
test can monkeypatch `_call_groq` to raise, deliberately simulating a
blocked primary path (CORRIX_BUILD_PLAN.md Step 4's own DoD item) without
needing to actually exhaust Groq's real rate limit.

Retry behavior: the Groq SDK's own default retry (`max_retries=2`) honors
whatever `Retry-After` the server returns, which on a real TPD/TPM
exhaustion can be 50+ seconds. Left to the SDK, a single call can block
for minutes before this module ever sees a failure to fall back to
Gemini on, which is bad both for the live demo (a Council convening
stalling mid-conversation) and for a batch script running dozens of
convenings back to back (found the hard way during Step 9's memory-loop
experiment reruns). So the SDK's own retrying is disabled
(`max_retries=0`) and replaced with a short, bounded retry loop here:
at most `groq_max_consecutive_429s` attempts, waiting the server's own
`Retry-After` if present and short, otherwise a small exponential
backoff with jitter, capped well below what a real TPD exhaustion would
report, then falling back to Gemini rather than continuing to wait.

`_request_semaphore` bounds how many Groq/Gemini calls run at once across
the whole process. Four evidence agents run concurrently within one
Council convening (`app/council/graph.py`), which is the graph's actual,
intentional concurrency; the default limit here is set high enough not
to constrain that. A batch script evaluating many scenarios in a row can
set `LLM_MAX_CONCURRENT_REQUESTS` lower via `.env` to stay under a
free-tier TPM budget without touching the live Council's own behavior.
"""

import logging
import random
import threading
import time
from dataclasses import dataclass
from typing import Literal

from google import genai
from groq import Groq, RateLimitError

from app.config import get_settings

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.1-8b-instant"
GEMINI_MODEL = "gemini-flash-latest"

Backend = Literal["groq", "gemini"]

_semaphore_lock = threading.Lock()
_request_semaphore: threading.Semaphore | None = None


def _get_request_semaphore() -> threading.Semaphore:
    """Lazily built from settings, once per process; a plain module-level
    semaphore would freeze the limit at import time, before `.env` (and
    any test override of `get_settings`) is necessarily loaded."""
    global _request_semaphore
    with _semaphore_lock:
        if _request_semaphore is None:
            limit = max(1, get_settings().llm_max_concurrent_requests)
            _request_semaphore = threading.Semaphore(limit)
    return _request_semaphore


@dataclass
class LLMResponse:
    text: str
    backend: Backend


def _retry_after_seconds(exc: RateLimitError, cap: float) -> float:
    header = exc.response.headers.get("retry-after")
    if header is not None:
        try:
            return min(float(header), cap)
        except ValueError:
            pass
    return cap


def _call_groq(system_prompt: str, user_prompt: str, max_tokens: int) -> str:
    settings = get_settings()
    client = Groq(api_key=settings.groq_api_key, max_retries=0)
    max_attempts = max(1, settings.groq_max_consecutive_429s)
    backoff_cap = settings.groq_retry_backoff_cap_seconds

    last_error: RateLimitError | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            with _get_request_semaphore():
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
        except RateLimitError as exc:
            last_error = exc
            if attempt < max_attempts:
                wait = _retry_after_seconds(exc, backoff_cap)
                jittered = min(backoff_cap, wait) + random.uniform(0, 1)
                logger.warning(
                    "Groq rate limit hit (attempt %d/%d), waiting %.1fs before retry",
                    attempt, max_attempts, jittered,
                )
                time.sleep(jittered)
    assert last_error is not None
    raise last_error


def _call_gemini(system_prompt: str, user_prompt: str, max_tokens: int) -> str:
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    with _get_request_semaphore():
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=f"{system_prompt}\n\n{user_prompt}",
        )
    return response.text


def chat_completion(
    system_prompt: str, user_prompt: str, max_tokens: int = 300
) -> LLMResponse:
    """Try Groq first (with its own short, bounded retry on a rate limit);
    on any failure, fall back to Gemini once. If both fail, the second
    exception propagates. There is no third path."""
    try:
        text = _call_groq(system_prompt, user_prompt, max_tokens)
        return LLMResponse(text=text, backend="groq")
    except Exception as groq_error:
        logger.warning("Groq call failed, falling back to Gemini: %s", groq_error)
        text = _call_gemini(system_prompt, user_prompt, max_tokens)
        return LLMResponse(text=text, backend="gemini")
