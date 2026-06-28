from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from research_pdf_vault.db import SCHEMA_VERSION, initialize_database
from research_pdf_vault.scan_db_models import (
    InstanceRecord,
    PaperRecord,
    ReadyFileIdentity,
    ScanBatch,
    ScanDataError,
    ScannedFile,
)
from research_pdf_vault.scan_ids import (
    HASH_ID_LENGTH,
    instance_id_from_result,
    instance_id_from_sha,
    paper_id_from_result,
    paper_id_from_sha,
)
from research_pdf_vault.sync_ready import SyncReadyResult

SCAN_SQL: Final = "\n".join(
    (
        "CREATE TABLE IF NOT EXISTS filesystem_snapshot (file_path TEXT PRIMARY KEY, observed_at TEXT NOT NULL, size_bytes INTEGER, mtime_ns INTEGER, sha256 TEXT CHECK (sha256 IS NULL OR length(sha256) = 64), sync_status TEXT NOT NULL, provider_status TEXT);",
        "CREATE TABLE IF NOT EXISTS pending_sync (file_path TEXT PRIMARY KEY, instance_id TEXT NOT NULL REFERENCES paper_instance(instance_id), last_reason TEXT NOT NULL, retry_count INTEGER NOT NULL CHECK (retry_count >= 1), last_attempt_at TEXT NOT NULL, next_retry_at TEXT NOT NULL, provider_status TEXT);",
    ),
)


def initialize_scan_database(connection: sqlite3.Connection) -> None:
    initialize_database(connection)
    connection.executescript(SCAN_SQL)


def now_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def relative_scan_path(storage_root: Path, source_path: Path) -> str:
    try:
        relative = source_path.resolve().relative_to(storage_root.resolve())
    except ValueError as error:
        raise ScanDataError(f"scan path is outside storage root: {source_path}") from error
    return (Path(storage_root.name) / relative).as_posix()


def record_ready(connection: sqlite3.Connection, batch: ScanBatch, item: ScannedFile) -> None:
    sha256 = _required_sha(item)
    paper_id = paper_id_from_sha(sha256)
    identity = ReadyFileIdentity(relative_path=item.relative_path, sha256=sha256)
    instance_id = _instance_for_ready(connection, identity, batch)
    _record_snapshot(connection, batch, item)
    _insert_paper(connection, _paper_record(paper_id, item, batch))
    _upsert_instance(
        connection,
        InstanceRecord(
            instance_id=instance_id,
            paper_id=paper_id,
            item=item,
            status="available",
            observed_at=batch.observed_at,
        ),
    )
    connection.execute(
        "DELETE FROM pending_sync WHERE file_path = ? OR instance_id = ?",
        (item.relative_path, instance_id),
    )


def record_snapshot_only(
    connection: sqlite3.Connection,
    batch: ScanBatch,
    item: ScannedFile,
) -> None:
    _record_snapshot(connection, batch, item)


def record_pending(
    connection: sqlite3.Connection,
    batch: ScanBatch,
    item: ScannedFile,
) -> None:
    paper_id = paper_id_from_result(item)
    instance_id = _existing_instance_for_path(connection, item.relative_path)
    if instance_id is None:
        instance_id = instance_id_from_result(item)
    _record_snapshot(connection, batch, item)
    _insert_paper(connection, _paper_record(paper_id, item, batch))
    _upsert_instance(
        connection,
        InstanceRecord(
            instance_id=instance_id,
            paper_id=paper_id,
            item=item,
            status="pending_sync",
            observed_at=batch.observed_at,
        ),
    )
    next_retry = _next_retry_timestamp(batch.observed_at, item.result)
    connection.execute(
        "INSERT INTO pending_sync (file_path, instance_id, last_reason, retry_count, last_attempt_at, next_retry_at, provider_status) VALUES (?, ?, ?, 1, ?, ?, ?) "
        "ON CONFLICT(file_path) DO UPDATE SET instance_id = excluded.instance_id, last_reason = excluded.last_reason, retry_count = retry_count + 1, last_attempt_at = excluded.last_attempt_at, next_retry_at = excluded.next_retry_at, provider_status = excluded.provider_status",
        (
            item.relative_path,
            instance_id,
            item.result.status.value,
            batch.observed_at,
            next_retry,
            item.result.provider_status,
        ),
    )


def mark_missing(connection: sqlite3.Connection, observed_paths: frozenset[str]) -> int:
    if not observed_paths:
        result = connection.execute(
            "UPDATE paper_instance SET instance_status = 'missing' WHERE instance_status != 'missing'",
        )
        connection.execute("UPDATE filesystem_snapshot SET sync_status = 'missing_path'")
        return result.rowcount
    placeholders = ",".join("?" for _ in observed_paths)
    result = connection.execute(
        f"UPDATE paper_instance SET instance_status = 'missing' WHERE file_path NOT IN ({placeholders}) AND instance_status != 'missing'",
        tuple(sorted(observed_paths)),
    )
    connection.execute(
        f"UPDATE filesystem_snapshot SET sync_status = 'missing_path' WHERE file_path NOT IN ({placeholders})",
        tuple(sorted(observed_paths)),
    )
    return result.rowcount


def _record_snapshot(
    connection: sqlite3.Connection,
    batch: ScanBatch,
    item: ScannedFile,
) -> None:
    connection.execute(
        "INSERT INTO filesystem_snapshot (file_path, observed_at, size_bytes, mtime_ns, sha256, sync_status, provider_status) VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(file_path) DO UPDATE SET observed_at = excluded.observed_at, size_bytes = excluded.size_bytes, mtime_ns = excluded.mtime_ns, sha256 = excluded.sha256, sync_status = excluded.sync_status, provider_status = excluded.provider_status",
        (
            item.relative_path,
            batch.observed_at,
            item.result.size_bytes,
            item.result.mtime_ns,
            item.result.sha256,
            item.result.status.value,
            item.result.provider_status,
        ),
    )


def _paper_record(paper_id: str, _item: ScannedFile, batch: ScanBatch) -> PaperRecord:
    return PaperRecord(
        paper_id=paper_id,
        title="Untitled scanned paper",
        observed_at=batch.observed_at,
    )


def _insert_paper(connection: sqlite3.Connection, record: PaperRecord) -> None:
    connection.execute(
        "INSERT INTO paper (schema_version, paper_id, title, normalized_identifiers, lane, created_at) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(paper_id) DO NOTHING",
        (
            SCHEMA_VERSION,
            record.paper_id,
            record.title,
            '{"source":"scan"}',
            "green",
            record.observed_at,
        ),
    )


def _upsert_instance(connection: sqlite3.Connection, record: InstanceRecord) -> None:
    connection.execute(
        "INSERT INTO paper_instance (schema_version, instance_id, paper_id, file_path, sha256, instance_status, discovered_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(instance_id) DO UPDATE SET paper_id = excluded.paper_id, file_path = excluded.file_path, sha256 = excluded.sha256, instance_status = excluded.instance_status",
        (
            SCHEMA_VERSION,
            record.instance_id,
            record.paper_id,
            record.item.relative_path,
            record.item.result.sha256,
            record.status,
            record.observed_at,
        ),
    )


def _instance_for_ready(
    connection: sqlite3.Connection,
    identity: ReadyFileIdentity,
    batch: ScanBatch,
) -> str:
    existing = _existing_instance_for_path(connection, identity.relative_path)
    if existing is not None:
        return existing
    moved = _moved_instance_for_sha(connection, identity, batch.observed_paths)
    if moved is not None:
        return moved
    return instance_id_from_sha(identity.sha256)


def _existing_instance_for_path(
    connection: sqlite3.Connection,
    relative_path: str,
) -> str | None:
    row = connection.execute(
        "SELECT instance_id FROM paper_instance WHERE file_path = ?",
        (relative_path,),
    ).fetchone()
    if row is None:
        return None
    return str(row[0])


def _moved_instance_for_sha(
    connection: sqlite3.Connection,
    identity: ReadyFileIdentity,
    observed_paths: frozenset[str],
) -> str | None:
    rows = connection.execute(
        "SELECT instance_id, file_path FROM paper_instance WHERE sha256 = ?",
        (identity.sha256,),
    )
    for instance_id, file_path in rows:
        if str(file_path) not in observed_paths:
            return str(instance_id)
    return None


def _required_sha(item: ScannedFile) -> str:
    if item.result.sha256 is None:
        raise ScanDataError(f"ready scan result has no hash: {item.relative_path}")
    return item.result.sha256


def _next_retry_timestamp(observed_at: str, result: SyncReadyResult) -> str:
    seconds = result.retry_after_seconds if result.retry_after_seconds is not None else 0
    parsed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    return (parsed + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")
