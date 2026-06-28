from __future__ import annotations

import sqlite3
from typing import Final

SCHEMA_VERSION: Final = "1.0.0"
CANONICAL_TABLES: Final[tuple[str, ...]] = (
    "vault_config",
    "paper",
    "paper_instance",
    "classification_decision",
    "review_queue_item",
    "audit_log",
    "extracted_passage",
    "claim_card",
    "citation_slot",
    "worker_report",
    "artifact_status",
    "literature_node",
    "literature_edge",
)

INIT_SQL: Final = "\n".join(
    (
        "PRAGMA foreign_keys = ON;",
        "CREATE TABLE IF NOT EXISTS vault_config (schema_version TEXT NOT NULL CHECK (schema_version = '1.0.0'), vault_id TEXT PRIMARY KEY CHECK (vault_id GLOB 'vault_*'), root_path TEXT NOT NULL CHECK (length(root_path) > 0 AND root_path NOT GLOB '/*' AND root_path != '..' AND root_path NOT GLOB '../*' AND root_path NOT GLOB '*/../*'), created_at TEXT NOT NULL, default_lane TEXT NOT NULL CHECK (default_lane IN ('green', 'amber', 'red')));",
        "CREATE TABLE IF NOT EXISTS paper (schema_version TEXT NOT NULL CHECK (schema_version = '1.0.0'), paper_id TEXT PRIMARY KEY CHECK (paper_id GLOB 'paper_*'), title TEXT NOT NULL CHECK (length(title) > 0), normalized_identifiers TEXT NOT NULL CHECK (length(normalized_identifiers) > 2), lane TEXT NOT NULL CHECK (lane IN ('green', 'amber', 'red')), created_at TEXT NOT NULL);",
        "CREATE TRIGGER IF NOT EXISTS paper_id_immutable BEFORE UPDATE OF paper_id ON paper BEGIN SELECT RAISE(ABORT, 'paper_id is immutable'); END;",
        "CREATE TABLE IF NOT EXISTS paper_instance (schema_version TEXT NOT NULL CHECK (schema_version = '1.0.0'), instance_id TEXT PRIMARY KEY CHECK (instance_id GLOB 'instance_*'), paper_id TEXT NOT NULL REFERENCES paper(paper_id), file_path TEXT NOT NULL CHECK (length(file_path) > 0 AND file_path NOT GLOB '/*' AND file_path != '..' AND file_path NOT GLOB '../*' AND file_path NOT GLOB '*/../*'), sha256 TEXT CHECK (sha256 IS NULL OR length(sha256) = 64), instance_status TEXT NOT NULL CHECK (instance_status IN ('available', 'missing', 'pending_sync', 'quarantined')), discovered_at TEXT NOT NULL);",
        "CREATE TABLE IF NOT EXISTS classification_decision (schema_version TEXT NOT NULL CHECK (schema_version = '1.0.0'), decision_id TEXT PRIMARY KEY CHECK (decision_id GLOB 'decision_*'), paper_id TEXT NOT NULL REFERENCES paper(paper_id), lane TEXT NOT NULL CHECK (lane IN ('green', 'amber', 'red')), stage_status TEXT NOT NULL CHECK (stage_status IN ('pending', 'running', 'complete', 'failed', 'quarantined')), actor TEXT NOT NULL, timestamp TEXT NOT NULL, reason TEXT NOT NULL CHECK (length(reason) > 0));",
        "CREATE TABLE IF NOT EXISTS review_queue_item (schema_version TEXT NOT NULL CHECK (schema_version = '1.0.0'), queue_item_id TEXT PRIMARY KEY CHECK (queue_item_id GLOB 'queue_*'), paper_id TEXT NOT NULL REFERENCES paper(paper_id), lane TEXT NOT NULL CHECK (lane IN ('green', 'amber', 'red')), stage_status TEXT NOT NULL CHECK (stage_status IN ('pending', 'running', 'complete', 'failed', 'quarantined')), priority TEXT NOT NULL CHECK (priority IN ('low', 'normal', 'high')), reason TEXT NOT NULL CHECK (length(reason) > 0), created_at TEXT NOT NULL);",
        "CREATE TABLE IF NOT EXISTS audit_log (schema_version TEXT NOT NULL CHECK (schema_version = '1.0.0'), audit_id TEXT PRIMARY KEY CHECK (audit_id GLOB 'audit_*'), paper_id TEXT NOT NULL REFERENCES paper(paper_id), actor TEXT NOT NULL, timestamp TEXT NOT NULL, action TEXT NOT NULL CHECK (action IN ('create', 'update', 'classify', 'quarantine', 'release')), reason TEXT NOT NULL CHECK (length(reason) > 0));",
        "CREATE TABLE IF NOT EXISTS extracted_passage (schema_version TEXT NOT NULL CHECK (schema_version = '1.0.0'), passage_id TEXT PRIMARY KEY CHECK (passage_id GLOB 'passage_*'), paper_id TEXT NOT NULL REFERENCES paper(paper_id), instance_id TEXT NOT NULL REFERENCES paper_instance(instance_id), source_page INTEGER NOT NULL CHECK (source_page >= 1), start_offset INTEGER NOT NULL CHECK (start_offset >= 0), end_offset INTEGER NOT NULL CHECK (end_offset > start_offset), text TEXT NOT NULL CHECK (length(text) > 0), support_tag TEXT NOT NULL CHECK (support_tag IN ('supports', 'contradicts', 'mixed', 'context')));",
        "CREATE TABLE IF NOT EXISTS claim_card (schema_version TEXT NOT NULL CHECK (schema_version = '1.0.0'), claim_id TEXT PRIMARY KEY CHECK (claim_id GLOB 'claim_*'), paper_id TEXT NOT NULL REFERENCES paper(paper_id), passage_id TEXT NOT NULL REFERENCES extracted_passage(passage_id), claim_text TEXT NOT NULL CHECK (length(claim_text) > 0), support_tag TEXT NOT NULL CHECK (support_tag IN ('supports', 'contradicts', 'mixed', 'context')), source_page INTEGER NOT NULL CHECK (source_page >= 1), start_offset INTEGER NOT NULL CHECK (start_offset >= 0), end_offset INTEGER NOT NULL CHECK (end_offset > start_offset));",
        "CREATE TABLE IF NOT EXISTS citation_slot (schema_version TEXT NOT NULL CHECK (schema_version = '1.0.0'), citation_slot_id TEXT PRIMARY KEY CHECK (citation_slot_id GLOB 'slot_*'), paper_id TEXT NOT NULL REFERENCES paper(paper_id), claim_id TEXT NOT NULL REFERENCES claim_card(claim_id), slot_label TEXT NOT NULL CHECK (length(slot_label) > 0), source_page INTEGER NOT NULL CHECK (source_page >= 1), start_offset INTEGER NOT NULL CHECK (start_offset >= 0), end_offset INTEGER NOT NULL CHECK (end_offset > start_offset), support_tag TEXT NOT NULL CHECK (support_tag IN ('supports', 'contradicts', 'mixed', 'context')));",
        "CREATE TABLE IF NOT EXISTS worker_report (schema_version TEXT NOT NULL CHECK (schema_version = '1.0.0'), report_id TEXT PRIMARY KEY CHECK (report_id GLOB 'report_*'), worker_name TEXT NOT NULL, paper_id TEXT NOT NULL REFERENCES paper(paper_id), stage_status TEXT NOT NULL CHECK (stage_status IN ('pending', 'running', 'complete', 'failed', 'quarantined')), started_at TEXT NOT NULL, finished_at TEXT NOT NULL, artifact_digest TEXT NOT NULL CHECK (artifact_digest GLOB 'sha256:*' AND length(artifact_digest) = 71), summary TEXT NOT NULL CHECK (length(summary) > 0));",
        "CREATE TABLE IF NOT EXISTS artifact_status (schema_version TEXT NOT NULL CHECK (schema_version = '1.0.0'), artifact_id TEXT PRIMARY KEY CHECK (artifact_id GLOB 'artifact_*'), paper_id TEXT NOT NULL REFERENCES paper(paper_id), artifact_kind TEXT NOT NULL CHECK (artifact_kind IN ('metadata', 'extracted_text', 'ocr_text', 'vector_index', 'claim_cards', 'citations', 'worker_report')), lane TEXT NOT NULL CHECK (lane IN ('green', 'amber', 'red')), stage_status TEXT NOT NULL CHECK (stage_status IN ('pending', 'running', 'complete', 'failed', 'quarantined')), artifact_digest TEXT NOT NULL CHECK (artifact_digest GLOB 'sha256:*' AND length(artifact_digest) = 71), created_at TEXT NOT NULL, artifact_path TEXT CHECK (artifact_path IS NULL OR (length(artifact_path) > 0 AND artifact_path NOT GLOB '/*' AND artifact_path != '..' AND artifact_path NOT GLOB '../*' AND artifact_path NOT GLOB '*/../*')), vector_artifact_path TEXT CHECK (vector_artifact_path IS NULL OR (length(vector_artifact_path) > 0 AND vector_artifact_path NOT GLOB '/*' AND vector_artifact_path != '..' AND vector_artifact_path NOT GLOB '../*' AND vector_artifact_path NOT GLOB '*/../*')), CHECK (vector_artifact_path IS NULL OR (lane != 'red' AND stage_status != 'quarantined')));",
        "CREATE TABLE IF NOT EXISTS literature_node (schema_version TEXT NOT NULL CHECK (schema_version = '1.0.0'), node_id TEXT PRIMARY KEY CHECK (node_id GLOB 'lnode_*'), node_kind TEXT NOT NULL CHECK (node_kind IN ('paper', 'claim', 'theory', 'method', 'construct', 'finding')), label TEXT NOT NULL CHECK (length(label) > 0), paper_id TEXT REFERENCES paper(paper_id), created_at TEXT NOT NULL);",
        "CREATE TABLE IF NOT EXISTS literature_edge (schema_version TEXT NOT NULL CHECK (schema_version = '1.0.0'), edge_id TEXT PRIMARY KEY CHECK (edge_id GLOB 'ledge_*'), source_node_id TEXT NOT NULL REFERENCES literature_node(node_id), target_node_id TEXT NOT NULL REFERENCES literature_node(node_id), edge_kind TEXT NOT NULL CHECK (edge_kind IN ('uses_method', 'tests_theory', 'measures_construct', 'supports_claim', 'contradicts', 'extends', 'analogy_only', 'requires_review')), evidence_paper_id TEXT REFERENCES paper(paper_id), confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0), created_at TEXT NOT NULL);",
    ),
)


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(INIT_SQL)
