"""Shared test fixtures/helpers.

`skip_on_rate_limit` wraps tests that make real Groq/Gemini calls: a
genuine 429 from either provider's free tier (heavily exercised by this
project's own test suite, which is exactly the kind of usage
CORRIX_PROJECT.md §7.1 warns is a real constraint) is an external quota
fact, not a defect in the code under test — skip with a clear reason
instead of failing the suite. Also covers a genuine 503 from Gemini
("this model is currently experiencing high demand") — the same class
of external, transient provider unavailability, not a code defect,
found during Step 8's own heavy real-call testing.
"""

from contextlib import contextmanager

import pytest

RATE_LIMIT_MARKERS = (
    "429",
    "RESOURCE_EXHAUSTED",
    "rate_limit_exceeded",
    "Rate limit reached",
    "503",
    "UNAVAILABLE",
    "currently experiencing high demand",
)


@contextmanager
def skip_on_rate_limit():
    try:
        yield
    except Exception as exc:
        message = str(exc)
        if any(marker in message for marker in RATE_LIMIT_MARKERS):
            pytest.skip(f"LLM provider rate limit hit during test: {exc}")
        raise
