from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

PDF_BYTES: Final = (
    b"%PDF-1.4\n"
    b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
    b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
    b"3 0 obj << /Type /Page /Parent 2 0 R >> endobj\n"
    b"%%EOF\n"
)


def write_config(config_path: Path) -> None:
    config_path.write_text(
        "\n".join(
            (
                'storage_roots = ["library"]',
                'cache_root = "cache"',
                'manifest_db = "cache/manifest.sqlite3"',
                'ocr_engine = "none"',
                'embedding_backend = "fixture"',
                'local_llm_backend = "disabled"',
                "enable_external_models = false",
                "max_external_passage_chars = 1200",
                "",
                "[review_thresholds]",
                "green_min_confidence = 0.86",
                "amber_review_max_confidence = 0.70",
                "red_min_confidence = 0.95",
                "",
                "[privacy]",
                "allow_cloud_cache = false",
                "red_lane_metadata_only = true",
                "allow_external_pdf_upload = false",
                "",
            ),
        ),
        encoding="utf-8",
    )


def load_rows(db_path: Path, query: str) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        return list(connection.execute(query))


def test_one_shot_scan_when_pdf_ready_then_records_available_instance(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.config import ConfigLoadRequest, load_config
    from research_pdf_vault.scanner import run_one_shot_scan

    # Given
    config_path = tmp_path / "rpv.toml"
    library = tmp_path / "library"
    library.mkdir()
    (library / "ready.pdf").write_bytes(PDF_BYTES)
    write_config(config_path)
    config = load_config(ConfigLoadRequest(config_path=config_path))

    # When
    summary = run_one_shot_scan(config)

    # Then
    assert summary.ready_count == 1
    instances = load_rows(
        config.manifest_db,
        "SELECT file_path, instance_status, sha256 FROM paper_instance",
    )
    assert len(instances) == 1
    assert instances[0]["file_path"] == "library/ready.pdf"
    assert instances[0]["instance_status"] == "available"
    assert len(instances[0]["sha256"]) == 64
    assert load_rows(config.manifest_db, "SELECT * FROM artifact_status") == []
    assert load_rows(config.manifest_db, "SELECT * FROM extracted_passage") == []


def test_one_shot_scan_when_pdf_is_not_ready_then_records_pending_sync(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.config import ConfigLoadRequest, load_config
    from research_pdf_vault.scanner import run_one_shot_scan

    # Given
    config_path = tmp_path / "rpv.toml"
    library = tmp_path / "library"
    library.mkdir()
    (library / "invalid.pdf").write_bytes(b"not a pdf\n%%EOF\n")
    write_config(config_path)
    config = load_config(ConfigLoadRequest(config_path=config_path))

    # When
    first = run_one_shot_scan(config)
    second = run_one_shot_scan(config)

    # Then
    assert first.pending_count == 1
    assert second.pending_count == 1
    instances = load_rows(
        config.manifest_db,
        "SELECT file_path, instance_status, sha256 FROM paper_instance",
    )
    assert len(instances) == 1
    assert instances[0]["file_path"] == "library/invalid.pdf"
    assert instances[0]["instance_status"] == "pending_sync"
    assert len(instances[0]["sha256"]) == 64
    pending_rows = load_rows(
        config.manifest_db,
        "SELECT file_path, last_reason, retry_count FROM pending_sync",
    )
    assert [dict(row) for row in pending_rows] == [
        {
            "file_path": "library/invalid.pdf",
            "last_reason": "invalid_pdf_header",
            "retry_count": 2,
        },
    ]
    assert load_rows(config.manifest_db, "SELECT * FROM artifact_status") == []
    assert load_rows(config.manifest_db, "SELECT * FROM extracted_passage") == []


def test_one_shot_scan_when_repeated_then_does_not_duplicate_instances(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.config import ConfigLoadRequest, load_config
    from research_pdf_vault.scanner import run_one_shot_scan

    # Given
    config_path = tmp_path / "rpv.toml"
    library = tmp_path / "library"
    library.mkdir()
    (library / "stable.pdf").write_bytes(PDF_BYTES)
    write_config(config_path)
    config = load_config(ConfigLoadRequest(config_path=config_path))

    # When
    run_one_shot_scan(config)
    run_one_shot_scan(config)

    # Then
    instance_count = load_rows(config.manifest_db, "SELECT COUNT(*) AS count FROM paper_instance")
    paper_count = load_rows(config.manifest_db, "SELECT COUNT(*) AS count FROM paper")
    assert instance_count[0]["count"] == 1
    assert paper_count[0]["count"] == 1


def test_one_shot_scan_when_file_moves_or_deletes_then_updates_existing_instance(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.config import ConfigLoadRequest, load_config
    from research_pdf_vault.scanner import run_one_shot_scan

    # Given
    config_path = tmp_path / "rpv.toml"
    library = tmp_path / "library"
    library.mkdir()
    original = library / "original.pdf"
    moved = library / "moved.pdf"
    original.write_bytes(PDF_BYTES)
    write_config(config_path)
    config = load_config(ConfigLoadRequest(config_path=config_path))
    run_one_shot_scan(config)
    original_row = load_rows(
        config.manifest_db,
        "SELECT instance_id, paper_id FROM paper_instance",
    )[0]

    # When
    original.rename(moved)
    run_one_shot_scan(config)
    moved.unlink()
    run_one_shot_scan(config)

    # Then
    rows = load_rows(
        config.manifest_db,
        "SELECT instance_id, paper_id, file_path, instance_status FROM paper_instance",
    )
    assert [dict(row) for row in rows] == [
        {
            "instance_id": original_row["instance_id"],
            "paper_id": original_row["paper_id"],
            "file_path": "library/moved.pdf",
            "instance_status": "missing",
        },
    ]
    paper_count = load_rows(config.manifest_db, "SELECT COUNT(*) AS count FROM paper")
    assert paper_count[0]["count"] == 1
