from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from research_pdf_vault.config import VaultRuntimeConfig
from research_pdf_vault.scan_classification import record_ready_classification
from research_pdf_vault.scan_db import (
    ScanBatch,
    ScannedFile,
    initialize_scan_database,
    mark_missing,
    now_timestamp,
    record_pending,
    record_ready,
    record_snapshot_only,
    relative_scan_path,
)
from research_pdf_vault.sync_ready import (
    SyncReadyResult,
    SyncReadyStatus,
    probe_sync_metadata,
    probe_sync_ready,
)


@dataclass(frozen=True, slots=True)
class ScanSummary:
    scanned_count: int
    ready_count: int
    pending_count: int
    missing_count: int
    dry_run_count: int


def run_one_shot_scan(config: VaultRuntimeConfig, *, dry_run: bool = False) -> ScanSummary:
    config.manifest_db.parent.mkdir(parents=True, exist_ok=True)
    observed_at = now_timestamp()
    scanned_files = tuple(_scan_files(config, dry_run=dry_run))
    batch = ScanBatch(
        observed_at=observed_at,
        observed_paths=frozenset(item.relative_path for item in scanned_files),
    )
    ready_count = sum(1 for item in scanned_files if item.result.ready)
    pending_count = len(scanned_files) - ready_count
    with sqlite3.connect(config.manifest_db) as connection:
        initialize_scan_database(connection)
        if dry_run:
            for item in scanned_files:
                record_snapshot_only(connection, batch, item)
            return ScanSummary(
                scanned_count=len(scanned_files),
                ready_count=ready_count,
                pending_count=pending_count,
                missing_count=0,
                dry_run_count=_dry_run_count(scanned_files),
            )
        for item in scanned_files:
            if item.result.ready:
                record_ready(connection, batch, item)
                record_ready_classification(connection, batch, item, config)
            else:
                record_pending(connection, batch, item)
        missing_count = mark_missing(connection, batch.observed_paths)
    return ScanSummary(
        scanned_count=len(scanned_files),
        ready_count=ready_count,
        pending_count=pending_count,
        missing_count=missing_count,
        dry_run_count=_dry_run_count(scanned_files),
    )


def _scan_files(
    config: VaultRuntimeConfig,
    *,
    dry_run: bool,
) -> tuple[ScannedFile, ...]:
    files: list[ScannedFile] = []
    for root in config.storage_roots:
        for source_path in _walk_root(root):
            result = _probe_file(config, source_path, dry_run=dry_run)
            files.append(
                ScannedFile(
                    source_path=source_path,
                    relative_path=relative_scan_path(root, source_path),
                    result=result,
                ),
            )
    return tuple(files)


def _probe_file(
    config: VaultRuntimeConfig,
    source_path: Path,
    *,
    dry_run: bool,
) -> SyncReadyResult:
    if dry_run:
        return probe_sync_metadata(source_path, config.sync.provider)
    return probe_sync_ready(source_path)


def _dry_run_count(scanned_files: tuple[ScannedFile, ...]) -> int:
    return sum(
        1
        for item in scanned_files
        if item.result.status is SyncReadyStatus.DRY_RUN_METADATA_ONLY
    )


def _walk_root(root: Path) -> tuple[Path, ...]:
    if not root.exists():
        return ()
    return tuple(
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() == ".pdf"
    )
