"""Shared test fixtures/helpers.

`skip_on_rate_limit` wraps tests that make real Groq/Gemini calls: a
genuine 429 from either provider's free tier (heavily exercised by this
project's own test suite, which is exactly the kind of usage
CORRIX_PROJECT.md §7.1 warns is a real constraint) is an external quota
fact, not a defect in the code under test — skip with a clear reason
instead of failing the suite.
"""

from contextlib import contextmanager

import pytest

RATE_LIMIT_MARKERS = (
    "429",
    "RESOURCE_EXHAUSTED",
    "rate_limit_exceeded",
    "Rate limit reached",
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
