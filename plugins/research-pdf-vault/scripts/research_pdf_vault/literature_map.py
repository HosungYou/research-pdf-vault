from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from typing import Final, assert_never

from research_pdf_vault.config import VaultRuntimeConfig
from research_pdf_vault.db import SCHEMA_VERSION, initialize_database
from research_pdf_vault.mcp_types import JsonObject
from research_pdf_vault.scan_db import now_timestamp
from research_pdf_vault.schema import Lane, SupportTag

NODE_ID_LENGTH: Final = 24


@dataclass(frozen=True, slots=True)
class LiteratureMapBuildSummary:
    node_count: int
    edge_count: int


def build_literature_map(config: VaultRuntimeConfig) -> LiteratureMapBuildSummary:
    config.manifest_db.parent.mkdir(parents=True, exist_ok=True)
    timestamp = now_timestamp()
    with sqlite3.connect(config.manifest_db) as connection:
        initialize_database(connection)
        _insert_paper_nodes(connection, timestamp)
        _insert_claim_nodes_and_edges(connection, timestamp)
        return LiteratureMapBuildSummary(
            node_count=_table_count(connection, "literature_node"),
            edge_count=_table_count(connection, "literature_edge"),
        )


def literature_map_report(config: VaultRuntimeConfig) -> JsonObject:
    if not config.manifest_db.exists():
        return _empty_report()
    with sqlite3.connect(config.manifest_db) as connection:
        initialize_database(connection)
        return {
            "graph_focus": "literature_map",
            "node_counts": _group_counts(connection, "literature_node", "node_kind"),
            "edge_counts": _group_counts(connection, "literature_edge", "edge_kind"),
        }


def _insert_paper_nodes(connection: sqlite3.Connection, timestamp: str) -> None:
    rows = connection.execute("SELECT paper_id, title, lane FROM paper ORDER BY paper_id")
    for paper_id, title, lane_value in rows:
        lane = Lane(str(lane_value))
        _upsert_node(
            connection,
            node_id=_node_id("paper", str(paper_id)),
            node_kind="paper",
            label=_paper_label(str(title), lane),
            paper_id=str(paper_id),
            timestamp=timestamp,
        )


def _insert_claim_nodes_and_edges(connection: sqlite3.Connection, timestamp: str) -> None:
    rows = connection.execute(
        "SELECT c.claim_id, c.paper_id, c.claim_text, c.support_tag, p.lane "
        "FROM claim_card c JOIN paper p ON p.paper_id = c.paper_id "
        "ORDER BY c.claim_id",
    )
    for claim_id, paper_id, claim_text, support_tag_value, lane_value in rows:
        lane = Lane(str(lane_value))
        claim_node_id = _node_id("claim", str(claim_id))
        paper_node_id = _node_id("paper", str(paper_id))
        edge_kind = _edge_kind_for_support(SupportTag(str(support_tag_value)))
        _upsert_node(
            connection,
            node_id=claim_node_id,
            node_kind="claim",
            label=_claim_label(str(claim_text), lane),
            paper_id=str(paper_id),
            timestamp=timestamp,
        )
        _upsert_edge(
            connection,
            edge_id=_edge_id(paper_node_id, claim_node_id, edge_kind),
            source_node_id=paper_node_id,
            target_node_id=claim_node_id,
            edge_kind=edge_kind,
            evidence_paper_id=str(paper_id),
            timestamp=timestamp,
        )


def _upsert_node(
    connection: sqlite3.Connection,
    *,
    node_id: str,
    node_kind: str,
    label: str,
    paper_id: str,
    timestamp: str,
) -> None:
    connection.execute(
        "INSERT INTO literature_node (schema_version, node_id, node_kind, label, paper_id, created_at) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(node_id) DO UPDATE SET node_kind = excluded.node_kind, label = excluded.label, paper_id = excluded.paper_id",
        (SCHEMA_VERSION, node_id, node_kind, label, paper_id, timestamp),
    )


def _upsert_edge(
    connection: sqlite3.Connection,
    *,
    edge_id: str,
    source_node_id: str,
    target_node_id: str,
    edge_kind: str,
    evidence_paper_id: str,
    timestamp: str,
) -> None:
    connection.execute(
        "INSERT INTO literature_edge (schema_version, edge_id, source_node_id, target_node_id, edge_kind, evidence_paper_id, confidence, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(edge_id) DO UPDATE SET edge_kind = excluded.edge_kind, evidence_paper_id = excluded.evidence_paper_id, confidence = excluded.confidence",
        (
            SCHEMA_VERSION,
            edge_id,
            source_node_id,
            target_node_id,
            edge_kind,
            evidence_paper_id,
            0.80,
            timestamp,
        ),
    )


def _paper_label(title: str, lane: Lane) -> str:
    match lane:
        case Lane.RED:
            return "Red paper (metadata-only)"
        case Lane.GREEN | Lane.AMBER:
            return title
        case unreachable:
            assert_never(unreachable)


def _claim_label(claim_text: str, lane: Lane) -> str:
    match lane:
        case Lane.RED:
            return "Red claim (metadata-only)"
        case Lane.GREEN | Lane.AMBER:
            return claim_text
        case unreachable:
            assert_never(unreachable)


def _edge_kind_for_support(support_tag: SupportTag) -> str:
    match support_tag:
        case SupportTag.SUPPORTS:
            return "supports_claim"
        case SupportTag.CONTRADICTS:
            return "contradicts"
        case SupportTag.MIXED | SupportTag.CONTEXT:
            return "requires_review"
        case unreachable:
            assert_never(unreachable)


def _group_counts(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
) -> JsonObject:
    rows = connection.execute(
        f"SELECT {column_name}, COUNT(*) FROM {table_name} GROUP BY {column_name} ORDER BY {column_name}",
    )
    return {str(kind): int(count) for kind, count in rows}


def _table_count(connection: sqlite3.Connection, table_name: str) -> int:
    row = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    return int(row[0])


def _empty_report() -> JsonObject:
    return {"graph_focus": "literature_map", "node_counts": {}, "edge_counts": {}}


def _node_id(kind: str, stable_id: str) -> str:
    return f"lnode_{kind}_{_digest(stable_id)}"


def _edge_id(source_node_id: str, target_node_id: str, edge_kind: str) -> str:
    return f"ledge_{_digest(':'.join((source_node_id, target_node_id, edge_kind)))}"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:NODE_ID_LENGTH]
