"""One-off verification that Step 1's Definition of Done credential
requirement is met: a real successful call against Groq, Gemini, and
Neo4j AuraDB. Prints only pass/fail per service, never the secret values.

Run from backend/: python scripts/verify_step1_credentials.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings


def verify_groq(api_key: str) -> None:
    from groq import Groq

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": "Reply with the single word: ok"}],
        max_tokens=5,
    )
    content = response.choices[0].message.content
    print(f"Groq: OK — response: {content!r}")


def verify_gemini(api_key: str) -> None:
    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents="Reply with the single word: ok",
    )
    print(f"Gemini: OK — response: {response.text!r}")


def verify_neo4j(uri: str, username: str, password: str) -> None:
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        driver.verify_connectivity()
        with driver.session() as session:
            result = session.run("RETURN 1 AS ok")
            record = result.single()
            print(f"Neo4j: OK — query result: {dict(record)}")
    finally:
        driver.close()


def main() -> None:
    settings = get_settings()
    failures = []

    for name, fn in [
        ("Groq", lambda: verify_groq(settings.groq_api_key)),
        ("Gemini", lambda: verify_gemini(settings.gemini_api_key)),
        (
            "Neo4j",
            lambda: verify_neo4j(
                settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password
            ),
        ),
    ]:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 — report every failure, don't stop early
            print(f"{name}: FAILED — {type(exc).__name__}: {exc}")
            failures.append(name)

    if failures:
        print(f"\n{len(failures)} service(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("\nAll three services verified successfully.")


if __name__ == "__main__":
    main()
