from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def test_scan_persistence_when_hashless_pending_then_path_is_not_identity(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.scan_db import (
        ScanBatch,
        ScannedFile,
        initialize_scan_database,
        record_pending,
    )
    from research_pdf_vault.sync_ready import SyncReadyResult, SyncReadyStatus

    # Given
    source_path = tmp_path / "filename-title.pdf"
    item = ScannedFile(
        source_path=source_path,
        relative_path="library/filename-title.pdf",
        result=SyncReadyResult(
            status=SyncReadyStatus.UNSTABLE_FILE,
            sha256=None,
            size_bytes=100,
            mtime_ns=200,
            retry_after_seconds=300,
        ),
    )
    batch = ScanBatch(
        observed_at="2026-01-01T00:00:00Z",
        observed_paths=frozenset((item.relative_path,)),
    )

    # When
    with sqlite3.connect(":memory:") as connection:
        initialize_scan_database(connection)
        record_pending(connection, batch, item)
        paper = connection.execute("SELECT paper_id, title FROM paper").fetchone()
        instance = connection.execute(
            "SELECT instance_id FROM paper_instance",
        ).fetchone()

    # Then
    assert not str(paper[0]).startswith("paper_path_")
    assert not str(instance[0]).startswith("instance_path_")
    assert paper[1] != "filename-title"


def test_scan_persistence_when_ready_file_moves_then_paper_id_survives(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.scan_db import (
        ScanBatch,
        ScannedFile,
        initialize_scan_database,
        record_ready,
    )
    from research_pdf_vault.sync_ready import SyncReadyResult, SyncReadyStatus

    # Given
    sha256 = "7" * 64
    original = ScannedFile(
        source_path=tmp_path / "original-name.pdf",
        relative_path="library/original-name.pdf",
        result=SyncReadyResult(
            status=SyncReadyStatus.READY,
            sha256=sha256,
            size_bytes=100,
            mtime_ns=200,
            retry_after_seconds=None,
        ),
    )
    moved = ScannedFile(
        source_path=tmp_path / "renamed.pdf",
        relative_path="library/renamed.pdf",
        result=SyncReadyResult(
            status=SyncReadyStatus.READY,
            sha256=sha256,
            size_bytes=100,
            mtime_ns=300,
            retry_after_seconds=None,
        ),
    )

    # When
    with sqlite3.connect(":memory:") as connection:
        initialize_scan_database(connection)
        record_ready(
            connection,
            ScanBatch(
                observed_at="2026-01-01T00:00:00Z",
                observed_paths=frozenset((original.relative_path,)),
            ),
            original,
        )
        before = connection.execute(
            "SELECT paper_id, instance_id FROM paper_instance",
        ).fetchone()
        record_ready(
            connection,
            ScanBatch(
                observed_at="2026-01-01T00:01:00Z",
                observed_paths=frozenset((moved.relative_path,)),
            ),
            moved,
        )
        after = connection.execute(
            "SELECT paper.paper_id, paper.title, paper_instance.instance_id, "
            "paper_instance.file_path FROM paper "
            "JOIN paper_instance ON paper.paper_id = paper_instance.paper_id",
        ).fetchone()

    # Then
    assert after[0] == before[0]
    assert not str(after[0]).startswith("paper_path_")
    assert not str(after[2]).startswith("instance_path_")
    assert after[1] != "original-name"
    assert after[3] == "library/renamed.pdf"
