"""Sanitizes free text before it can reach an LLM prompt, per
CORRIX_REAL_DATA_BUILD_PLAN.md Step 26. A character allow-list, not a
semantic prompt-injection filter (unrealistic at this scope): strips
anything outside plain alphanumeric text, spaces, and a small set of
common punctuation, including newlines specifically, since a fake
role marker or an "ignore previous instructions" style injection
typically relies on a newline to look like a new turn. Also collapses
whitespace and caps length, so a very long payload can't bloat a
prompt either.

Enforced on the backend, not just the frontend, since a direct API or
MQTT publish bypasses whatever the frontend already validates.

Checked against the actual data flow before writing this: neither the
wizard's zone-name field nor its "other permit" free text currently
reach any LLM prompt in the code as built (zone identification in
raw_evidence uses zone_id, an auto-generated "Z<n>" string, never the
user-typed name; the "other permit" text itself is never sent to the
backend at all, only a fixed "unmapped_permit_type" marker is). The
real, currently-exploitable vectors are badge_id and
linked_checklist_id, which arrive from a live MQTT message
(app/ingestion/mqtt_ingest.py) with no backend-side shape validation
on their string content, and do reach raw_evidence via
app/api/live_evidence.py's formatters. Applied there rather than only
in mqtt_ingest.py, so csv_ingest.py and any future opcua_ingest.py
badge/permit path get the same protection at a single choke point
instead of duplicating it per adapter.
"""

import re

_DISALLOWED_CHARS = re.compile(r"[^a-zA-Z0-9 .,'\-#/]")
DEFAULT_MAX_LENGTH = 200


def sanitize_for_prompt(text: str, max_length: int = DEFAULT_MAX_LENGTH) -> str:
    """Replaces characters outside a plain-text allow-list with a
    space (not deleted outright, so e.g. a newline can't silently glue
    two words together into a new one), collapses the resulting
    whitespace, and truncates to `max_length`. Never raises: a caller
    always gets back a usable string, just a cleaned one. Idempotent
    on already-clean text (authored scenario strings pass through
    unchanged), so this is safe to apply unconditionally at a shared
    choke point rather than only on suspected-untrusted input.

    This is a character allow-list, not a semantic filter: it removes
    the structural primitives a prompt injection typically relies on
    (a newline pretending to start a new turn, a colon pretending to
    be a role marker like "SYSTEM:"), not any English words that
    happen to survive. A full semantic defense is out of scope at this
    check's stated purpose and scale.
    """
    if not isinstance(text, str):
        return ""
    spaced = _DISALLOWED_CHARS.sub(" ", text)
    collapsed = " ".join(spaced.split())
    return collapsed[:max_length]
