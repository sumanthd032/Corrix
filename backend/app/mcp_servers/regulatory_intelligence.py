"""Regulatory Intelligence MCP Server.

One server covering RAG Q&A, pattern lookup, and compliance checking
against the unified Neo4j substrate (CORRIX_PROJECT.md §7.1, §8 Pillar 3;
CORRIX_DATA_METHODOLOGY.md §11). Real tools as of Step 5, backed by the
single Neo4j AuraDB instance — vector similarity, graph traversal, and
compliance checking all read from the same database, per the build
plan's explicit instruction not to split this into three servers.
"""

from mcp.server.fastmcp import FastMCP
from neo4j import GraphDatabase

from app.config import get_settings
from app.regulatory.retrieval import (
    answer_regulatory_question,
    check_compliance as _check_compliance,
    lookup_incident_pattern as _lookup_incident_pattern,
)

server = FastMCP("corrix-regulatory-intelligence")

_settings = get_settings()
_driver = GraphDatabase.driver(
    _settings.neo4j_uri, auth=(_settings.neo4j_username, _settings.neo4j_password)
)


@server.tool()
def query_regulatory_corpus(question: str, framework: str | None = None) -> dict:
    """Answer a regulatory question via vector similarity over the
    OISD/Factories Act/DGMS corpus. Pass framework="DGMS" to scope to
    DGMS content specifically — returns an honest "not yet ingested"
    note rather than a fabricated primary citation if none exists."""
    return answer_regulatory_question(_driver, question, framework=framework)


@server.tool()
def lookup_incident_pattern(permit_type: str, zone_hazard_class: str | None = None) -> dict:
    """Graph-traversal lookup: has a compound-risk pattern involving this
    permit type (optionally scoped to a zone hazard class) occurred
    before, per the mocked near-miss/audit-log corpus."""
    return _lookup_incident_pattern(_driver, permit_type, zone_hazard_class)


@server.tool()
def check_compliance(deviation_type: str) -> dict:
    """Match a deviation type against the mocked audit-log corpus and,
    if it's a known seeded deviation, flag it with the real clause it
    violates."""
    return _check_compliance(_driver, deviation_type)


if __name__ == "__main__":
    server.run_stdio_async()
