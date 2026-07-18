"""One-time Neo4j setup for a fresh clone.

A freshly-cloned Corrix has all the source material it needs committed to
the repo (the regulatory PDFs, the near-miss corpus, the plant layout),
but a brand-new Neo4j AuraDB instance is empty. This script populates it
so the live backend's Regulatory Intelligence features (the RAG chat,
pattern lookup, and compliance checks) and the self-improving memory
loop's schema are ready.

Run once, after filling in NEO4J_* in the repo-root .env:

    cd backend
    python scripts/setup_neo4j.py

It is idempotent: the schema uses IF NOT EXISTS and the ingestion uses
MERGE, so running it again is safe and simply re-asserts the same state.

What it does NOT do: populate the memory-loop *exemplars*. Those come
from real, LLM-heavy evaluation runs (scripts/run_memory_loop_experiment.py),
which take a long time and consume real Groq/Gemini quota, so they are a
separate, optional, advanced step. The regulatory features and the whole
frontend demo work without them; only the memory-retrieval trigger path
(scenario S5's live behavior) depends on stored exemplars.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from neo4j import GraphDatabase  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.memory.exemplar_store import ensure_memory_schema  # noqa: E402
from app.regulatory.loader import ingest_all  # noqa: E402

SOURCES_DIR = Path(__file__).resolve().parents[2] / "data" / "regulatory" / "sources"


def main() -> None:
    settings = get_settings()
    if not settings.neo4j_uri:
        print(
            "NEO4J_URI is not set. Copy .env.example to .env at the repo root "
            "and fill in your Neo4j AuraDB credentials first."
        )
        raise SystemExit(1)

    print(f"Connecting to Neo4j at {settings.neo4j_uri} ...")
    driver = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password)
    )
    try:
        print("Ingesting the regulatory corpus (schema, zones, equipment, permits, clauses, incidents) ...")
        counts = ingest_all(driver, SOURCES_DIR)
        print("Ensuring the memory-exemplar schema ...")
        ensure_memory_schema(driver)
    finally:
        driver.close()

    print("\nDone. Ingested:")
    for key, value in counts.items():
        if value is not None:
            print(f"  {key}: {value}")
    print(
        "\nThe live backend's Regulatory Intelligence features are now ready. "
        "The memory-loop exemplars are optional and populated separately via "
        "scripts/run_memory_loop_experiment.py (advanced, LLM-heavy)."
    )


if __name__ == "__main__":
    main()
