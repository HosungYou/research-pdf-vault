from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from typing import Final

from research_pdf_vault.db import SCHEMA_VERSION
from research_pdf_vault.scan_db import now_timestamp
from research_pdf_vault.schema import (
    ArtifactDigest,
    InstanceId,
    Lane,
    PaperId,
    StageStatus,
)

VECTOR_ARTIFACT_PATH: Final = "index/chunk_embedding"
FTS_ARTIFACT_PATH: Final = "index/chunk_fts"
_STATUS_ID_LENGTH: Final = 24


@dataclass(frozen=True, slots=True)
class IndexCandidate:
    paper_id: PaperId
    instance_id: InstanceId
    file_path: str
    lane: Lane
    normalized_identifiers: str


@dataclass(frozen=True, slots=True)
class IndexStatusResult:
    stage_status: StageStatus
    artifact_digest: ArtifactDigest
    vector_artifact_path: str | None


def upsert_artifact_status(
    connection: sqlite3.Connection,
    candidate: IndexCandidate,
    result: IndexStatusResult,
) -> None:
    connection.execute(
        "INSERT INTO artifact_status (schema_version, artifact_id, paper_id, artifact_kind, lane, stage_status, artifact_digest, created_at, artifact_path, vector_artifact_path) "
        "VALUES (?, ?, ?, 'vector_index', ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(artifact_id) DO UPDATE SET lane = excluded.lane, stage_status = excluded.stage_status, artifact_digest = excluded.artifact_digest, created_at = excluded.created_at, artifact_path = excluded.artifact_path, vector_artifact_path = excluded.vector_artifact_path",
        (
            SCHEMA_VERSION,
            _artifact_id(candidate.paper_id),
            candidate.paper_id,
            candidate.lane.value,
            result.stage_status.value,
            result.artifact_digest,
            now_timestamp(),
            FTS_ARTIFACT_PATH,
            result.vector_artifact_path,
        ),
    )


def record_quarantine_audit(
    connection: sqlite3.Connection,
    candidate: IndexCandidate,
) -> None:
    connection.execute(
        "INSERT INTO audit_log (schema_version, audit_id, paper_id, actor, timestamp, action, reason) "
        "VALUES (?, ?, ?, 'index_builder', ?, 'quarantine', 'red lane cannot be indexed') "
        "ON CONFLICT(audit_id) DO UPDATE SET timestamp = excluded.timestamp, reason = excluded.reason",
        (
            SCHEMA_VERSION,
            f"audit_index_{_digest_text(candidate.paper_id)[:_STATUS_ID_LENGTH]}",
            candidate.paper_id,
            now_timestamp(),
        ),
    )


def status_result(
    stage_status: StageStatus,
    candidate: IndexCandidate,
    reason: str,
) -> IndexStatusResult:
    digest = _digest_text(
        "\n".join((candidate.paper_id, candidate.instance_id, stage_status.value, reason)),
    )
    return IndexStatusResult(
        stage_status=stage_status,
        artifact_digest=ArtifactDigest(f"sha256:{digest}"),
        vector_artifact_path=None,
    )


def _artifact_id(paper_id: PaperId) -> str:
    return f"artifact_vector_{_digest_text(paper_id)[:_STATUS_ID_LENGTH]}"


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
