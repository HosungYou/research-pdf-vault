from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Final

from research_pdf_vault.config import VaultRuntimeConfig
from research_pdf_vault.db import SCHEMA_VERSION, initialize_database
from research_pdf_vault.mcp_types import JsonObject
from research_pdf_vault.scan_db import now_timestamp

CONSTRUCT_SQL: Final = "\n".join(
    (
        "CREATE TABLE IF NOT EXISTS construct_registry (construct_id TEXT PRIMARY KEY CHECK (construct_id GLOB 'construct_*'), canonical_label TEXT NOT NULL CHECK (length(canonical_label) > 0), aliases_json TEXT NOT NULL CHECK (length(aliases_json) > 1), definition_notes TEXT NOT NULL, measurement_families_json TEXT NOT NULL CHECK (length(measurement_families_json) > 1), theory_links_json TEXT NOT NULL CHECK (length(theory_links_json) > 1), merge_status TEXT NOT NULL CHECK (merge_status IN ('candidate', 'approved', 'merged', 'rejected')), review_status TEXT NOT NULL CHECK (review_status IN ('auto', 'needs_review', 'approved', 'rejected')), created_at TEXT NOT NULL);",
        "CREATE TABLE IF NOT EXISTS construct_candidate (candidate_id TEXT PRIMARY KEY CHECK (candidate_id GLOB 'ccand_*'), paper_id TEXT NOT NULL REFERENCES paper(paper_id), construct_id TEXT NOT NULL REFERENCES construct_registry(construct_id), reported_term TEXT NOT NULL CHECK (length(reported_term) > 0), candidate_normalization TEXT NOT NULL CHECK (length(candidate_normalization) > 0), measurement_proxy TEXT NOT NULL CHECK (length(measurement_proxy) > 0), theoretical_role TEXT NOT NULL CHECK (length(theoretical_role) > 0), confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0), review_required INTEGER NOT NULL CHECK (review_required IN (0, 1)), source_page INTEGER NOT NULL CHECK (source_page >= 1), created_at TEXT NOT NULL);",
    ),
)
_LINE_RE: Final = re.compile(
    r"Construct:\s*(?P<term>[^|\n]+)\|\s*Measurement:\s*(?P<measurement>[^|\n]+)\|\s*Role:\s*(?P<role>[^\n]+)",
    re.IGNORECASE,
)
_WORD_RE: Final = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class ConstructBuildSummary:
    registry_count: int
    candidate_count: int
    review_required_count: int


@dataclass(frozen=True, slots=True)
class ConstructCandidate:
    paper_id: str
    reported_term: str
    normalization: str
    measurement_proxy: str
    theoretical_role: str
    source_page: int


def initialize_construct_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(CONSTRUCT_SQL)


def build_construct_candidates(config: VaultRuntimeConfig) -> ConstructBuildSummary:
    config.manifest_db.parent.mkdir(parents=True, exist_ok=True)
    timestamp = now_timestamp()
    with sqlite3.connect(config.manifest_db) as connection:
        initialize_database(connection)
        initialize_construct_tables(connection)
        for candidate in _extract_candidates(connection):
            _upsert_construct_candidate(connection, candidate, timestamp)
        return _summary(connection)


def construct_report(config: VaultRuntimeConfig) -> ConstructBuildSummary:
    if not config.manifest_db.exists():
        return ConstructBuildSummary(0, 0, 0)
    with sqlite3.connect(config.manifest_db) as connection:
        initialize_database(connection)
        initialize_construct_tables(connection)
        return _summary(connection)


def construct_report_json(config: VaultRuntimeConfig) -> JsonObject:
    summary = construct_report(config)
    return {
        "graph_focus": "construct_registry",
        "registry_count": summary.registry_count,
        "candidate_count": summary.candidate_count,
        "review_required_count": summary.review_required_count,
    }


def _extract_candidates(connection: sqlite3.Connection) -> tuple[ConstructCandidate, ...]:
    rows = connection.execute(
        "SELECT paper_id, source_page, text FROM index_chunk ORDER BY paper_id, source_page, chunk_id",
    )
    candidates: list[ConstructCandidate] = []
    for paper_id, source_page, text in rows:
        for match in _LINE_RE.finditer(str(text)):
            reported_term = _clean(match.group("term"))
            candidates.append(
                ConstructCandidate(
                    paper_id=str(paper_id),
                    reported_term=reported_term,
                    normalization=_normalization(reported_term),
                    measurement_proxy=_clean(match.group("measurement")),
                    theoretical_role=_clean(match.group("role")).casefold(),
                    source_page=int(source_page),
                ),
            )
    return tuple(candidates)


def _upsert_construct_candidate(
    connection: sqlite3.Connection,
    candidate: ConstructCandidate,
    timestamp: str,
) -> None:
    construct_id = _construct_id(candidate.normalization)
    connection.execute(
        "INSERT INTO construct_registry (construct_id, canonical_label, aliases_json, definition_notes, measurement_families_json, theory_links_json, merge_status, review_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(construct_id) DO UPDATE SET aliases_json = excluded.aliases_json, measurement_families_json = excluded.measurement_families_json",
        (
            construct_id,
            candidate.normalization,
            json.dumps([candidate.reported_term], sort_keys=True),
            "",
            json.dumps([candidate.measurement_proxy], sort_keys=True),
            "[]",
            "candidate",
            "auto",
            timestamp,
        ),
    )
    connection.execute(
        "INSERT INTO construct_candidate (candidate_id, paper_id, construct_id, reported_term, candidate_normalization, measurement_proxy, theoretical_role, confidence, review_required, source_page, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(candidate_id) DO UPDATE SET reported_term = excluded.reported_term, candidate_normalization = excluded.candidate_normalization, measurement_proxy = excluded.measurement_proxy, theoretical_role = excluded.theoretical_role, confidence = excluded.confidence, review_required = excluded.review_required, source_page = excluded.source_page",
        (
            _candidate_id(candidate),
            candidate.paper_id,
            construct_id,
            candidate.reported_term,
            candidate.normalization,
            candidate.measurement_proxy,
            candidate.theoretical_role,
            0.86,
            0,
            candidate.source_page,
            timestamp,
        ),
    )


def _summary(connection: sqlite3.Connection) -> ConstructBuildSummary:
    return ConstructBuildSummary(
        registry_count=_table_count(connection, "construct_registry"),
        candidate_count=_table_count(connection, "construct_candidate"),
        review_required_count=_review_required_count(connection),
    )


def _clean(value: str) -> str:
    return " ".join(value.strip().split())


def _normalization(value: str) -> str:
    return " ".join(_WORD_RE.findall(value.casefold()))


def _construct_id(normalization: str) -> str:
    return f"construct_{_digest(normalization)}"


def _candidate_id(candidate: ConstructCandidate) -> str:
    stable = ":".join(
        (
            candidate.paper_id,
            candidate.normalization,
            candidate.measurement_proxy,
            candidate.theoretical_role,
        ),
    )
    return f"ccand_{_digest(stable)}"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _table_count(connection: sqlite3.Connection, table_name: str) -> int:
    row = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    return int(row[0])


def _review_required_count(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT COUNT(*) FROM construct_candidate WHERE review_required = 1",
    ).fetchone()
    return int(row[0])
