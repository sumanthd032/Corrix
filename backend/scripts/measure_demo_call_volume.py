"""Step 9's own DoD item: "measure actual LLM call volume against
free-tier limits during a realistic demo run-through (3 scenarios +
Q&A) and confirm it stays comfortably under Groq's 30 RPM." This was a
calculation in CORRIX_PROJECT.md §7.1 ("one Council convening is 5
calls; a demo cycling through 3 scenarios plus Q&A follow-ups is
comfortably under 30-40 calls in a short window"); this script is where
it becomes a real, timestamped measurement instead of an estimate.

Instruments the real Groq/Gemini SDK request methods (not this
project's own wrapper functions, and not a mock) with a timestamped
counter, so a request that gets rate-limited is counted the same as one
that succeeds: a 429 still consumes real RPM budget, and undercounting
failed attempts would understate exactly the volume most likely to
explain a demo hitting one. Runs an actual realistic demo sequence:
three real scenario Council convenings, paced 8 seconds apart the way a
presenter narrating between selections actually would (not a
zero-pause burst, which self-inflicts a TPM spike no real demo
produces), plus three real regulatory Q&A questions through the actual
RAG retrieval path (confirmed to cost zero LLM calls, being pure vector
retrieval). Reports total requests, success/failure split per backend,
peak requests in any rolling 60-second window, and headroom against
Groq's 30 RPM / Gemini's 15 RPM published free-tier limits.

Run from backend/: python scripts/measure_demo_call_volume.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.genai.models import Models  # noqa: E402
from groq.resources.chat.completions import Completions  # noqa: E402
from neo4j import GraphDatabase  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.council.graph import run_council  # noqa: E402
from app.council.sample_payloads import ALL_SAMPLE_PAYLOADS  # noqa: E402
from app.regulatory.retrieval import answer_regulatory_question  # noqa: E402

GROQ_RPM_LIMIT = 30
GEMINI_RPM_LIMIT = 15

CallLog = list[tuple[float, str, bool]]  # (timestamp, backend, succeeded)


def _instrument(call_log: CallLog):
    """Patches the SDKs' own request methods, not this project's
    `_call_groq`/`_call_gemini` wrappers: a request that gets rate-
    limited still counts against the provider's real RPM budget, so a
    call that failed must be counted the same as one that succeeded, or
    this measurement would systematically undercount exactly the
    attempts most likely to explain a demo hitting a real 429."""
    real_groq_create = Completions.create
    real_gemini_generate = Models.generate_content

    def logged_groq_create(self, *args, **kwargs):
        try:
            result = real_groq_create(self, *args, **kwargs)
            call_log.append((time.monotonic(), "groq", True))
            return result
        except Exception:
            call_log.append((time.monotonic(), "groq", False))
            raise

    def logged_gemini_generate(self, *args, **kwargs):
        try:
            result = real_gemini_generate(self, *args, **kwargs)
            call_log.append((time.monotonic(), "gemini", True))
            return result
        except Exception:
            call_log.append((time.monotonic(), "gemini", False))
            raise

    Completions.create = logged_groq_create
    Models.generate_content = logged_gemini_generate
    return real_groq_create, real_gemini_generate


def _restore(real_groq_create, real_gemini_generate):
    Completions.create = real_groq_create
    Models.generate_content = real_gemini_generate


def _peak_calls_in_window(timestamps: list[float], window_seconds: float = 60.0) -> int:
    peak = 0
    for i, t in enumerate(timestamps):
        count = sum(1 for other in timestamps[i:] if other - t <= window_seconds)
        peak = max(peak, count)
    return peak


def main() -> None:
    settings = get_settings()
    neo4j_driver = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password)
    )

    call_log: CallLog = []
    real_groq, real_gemini = _instrument(call_log)
    demo_start = time.monotonic()

    try:
        print("--- Realistic demo run-through: 3 scenarios + regulatory Q&A ---\n")

        for i, scenario_id in enumerate(["S1", "S2", "S4"]):
            if i > 0:
                # A real presenter narrates between scenario selections; a
                # machine-gun burst with zero pause between three
                # simultaneous 4-agent convenings is not what "a realistic
                # demo run-through" actually looks like, and self-inflicts
                # a TPM burst no real demo pacing would produce.
                time.sleep(8.0)
            payload = ALL_SAMPLE_PAYLOADS[scenario_id]
            t0 = time.monotonic()
            verdict = run_council(
                zone_id=payload["zone_id"],
                trigger_reason="rule_threshold",
                raw_evidence=payload,
                scenario_id=scenario_id,
                thread_id=f"demo-volume-{scenario_id}",
            )
            elapsed = time.monotonic() - t0
            print(
                f"[{scenario_id}] Council convening resolved in {elapsed:.1f}s -> "
                f"{verdict.risk_level} (confidence {verdict.confidence:.2f})"
            )

        questions = [
            "What precautions are required for explosive or flammable gas?",
            "Has a compound risk involving hot work permits happened before?",
            "Is a missing LEL reading a known compliance deviation?",
        ]
        for question in questions:
            t0 = time.monotonic()
            answer_regulatory_question(neo4j_driver, question)
            elapsed = time.monotonic() - t0
            print(f'[Q&A] "{question[:50]}..." answered in {elapsed:.2f}s (no LLM call)')

    finally:
        _restore(real_groq, real_gemini)
        neo4j_driver.close()

    demo_elapsed = time.monotonic() - demo_start
    groq_log = [t for t, backend, _ in call_log if backend == "groq"]
    gemini_log = [t for t, backend, _ in call_log if backend == "gemini"]
    groq_ok = sum(1 for _, backend, ok in call_log if backend == "groq" and ok)
    groq_failed = sum(1 for _, backend, ok in call_log if backend == "groq" and not ok)
    gemini_ok = sum(1 for _, backend, ok in call_log if backend == "gemini" and ok)
    gemini_failed = sum(1 for _, backend, ok in call_log if backend == "gemini" and not ok)
    peak_groq_60s = _peak_calls_in_window(groq_log, 60.0)
    peak_gemini_60s = _peak_calls_in_window(gemini_log, 60.0)

    print("\n--- Measured call volume ---")
    print(f"Total demo wall-clock time: {demo_elapsed:.1f}s")
    print(f"Total real Groq requests: {len(groq_log)} ({groq_ok} succeeded, {groq_failed} failed/retried)")
    print(f"Total real Gemini requests: {len(gemini_log)} ({gemini_ok} succeeded, {gemini_failed} failed/retried)")
    print(f"Peak Groq requests in any rolling 60s window: {peak_groq_60s}")
    print(f"Peak Gemini requests in any rolling 60s window: {peak_gemini_60s}")
    print(f"Groq free-tier limit: {GROQ_RPM_LIMIT} RPM -> headroom: {GROQ_RPM_LIMIT - peak_groq_60s} requests")
    print(f"Gemini free-tier limit: {GEMINI_RPM_LIMIT} RPM -> headroom: {GEMINI_RPM_LIMIT - peak_gemini_60s} requests")
    print(f"\nWithin Groq's 30 RPM: {peak_groq_60s <= GROQ_RPM_LIMIT}")
    print(f"Within Gemini's 15 RPM: {peak_gemini_60s <= GEMINI_RPM_LIMIT}")


if __name__ == "__main__":
    main()
