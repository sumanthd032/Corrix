"""Shared test fixtures/helpers.

`skip_on_rate_limit` wraps tests that make real Groq/Gemini calls: a
genuine 429 from either provider's free tier (heavily exercised by this
project's own test suite, which is exactly the kind of usage
CORRIX_PROJECT.md §7.1 warns is a real constraint) is an external quota
fact, not a defect in the code under test; skip with a clear reason
instead of failing the suite. Also covers a genuine 503 from Gemini
("this model is currently experiencing high demand"), the same class
of external, transient provider unavailability, not a code defect,
found during Step 8's own heavy real-call testing.
"""

import logging
import time
from contextlib import contextmanager

import pytest

from app.memory.exemplar_store import (
    ensure_memory_schema,
    get_all_exemplars,
    get_shared_driver,
    store_exemplar,
    wipe_all_exemplars,
)

logger = logging.getLogger(__name__)

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


@pytest.fixture(scope="session", autouse=True)
def _preserve_real_memory_exemplars():
    """Several tests (test_memory_loop.py, test_live_scenario.py) need a
    genuinely empty MemoryExemplar store as their precondition, to prove
    no retrieval trigger fires with nothing stored, so they wipe it. That
    store lives in the same shared, live Neo4j instance
    backend/scripts/run_memory_loop_experiment.py populates with real,
    load-bearing exemplars, not a disposable test fixture, and a plain
    wipe-at-teardown left the real exemplars permanently gone after any
    test run. This snapshots whatever is genuinely stored once, before
    any test can touch it, and restores exactly that snapshot once, after
    the whole session ends, so running the suite never permanently
    destroys real state.

    The restore itself is wrapped in a real retry: this project's own
    shared Neo4j AuraDB instance has hit genuine transient connectivity
    resets several times during this project's testing (a real,
    external fact, not a code defect), and the first version of this
    fixture had no protection against one landing during the restore
    itself, which is exactly what silently emptied the store once,
    caught only by a manual post-suite check rather than by the fixture
    being resilient to begin with."""
    driver = get_shared_driver()
    ensure_memory_schema(driver)
    snapshot = get_all_exemplars(driver)
    yield

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            wipe_all_exemplars(driver)
            for exemplar in snapshot:
                store_exemplar(
                    driver,
                    exemplar_id=exemplar.exemplar_id,
                    scenario_id=exemplar.scenario_id,
                    seed=exemplar.seed,
                    zone_id=exemplar.zone_id,
                    joint_evidence_vector=exemplar.joint_evidence_vector,
                    evidence_text=exemplar.evidence_text,
                    correct_risk_level=exemplar.correct_risk_level,
                    why=exemplar.why,
                )
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Exemplar restore attempt %d/3 hit a transient error, retrying: %s", attempt, exc
            )
            time.sleep(3.0)
    if last_error is not None:
        logger.error(
            "Exemplar restore failed after 3 attempts; real exemplars may be lost: %s", last_error
        )
