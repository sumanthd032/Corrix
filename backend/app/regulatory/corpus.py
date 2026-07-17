"""Loads the mocked near-miss/audit-log corpus, per
CORRIX_DATA_METHODOLOGY.md §10. Each entry validates as a Step 1
AuditLogEntry, plus two extra graph-only fields (`permit_type`,
`zone_hazard_class`) used to build the Neo4j INVOLVED_PERMIT_TYPE edge;
these aren't part of the locked AuditLogEntry schema since they exist
only to drive graph traversal, not the wire schema itself.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from app.schemas import AuditLogEntry

REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS_PATH = REPO_ROOT / "data" / "regulatory" / "corpus" / "near_miss_corpus.yaml"

_AUDIT_LOG_FIELDS = set(AuditLogEntry.model_fields.keys())


@dataclass
class IncidentRecord:
    audit_log_entry: AuditLogEntry
    permit_type: str
    zone_hazard_class: str


def load_near_miss_corpus(path: Path = CORPUS_PATH) -> list[IncidentRecord]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    records = []
    for raw in data["entries"]:
        audit_fields = {k: v for k, v in raw.items() if k in _AUDIT_LOG_FIELDS}
        records.append(
            IncidentRecord(
                audit_log_entry=AuditLogEntry(**audit_fields),
                permit_type=raw["permit_type"],
                zone_hazard_class=raw["zone_hazard_class"],
            )
        )
    return records
