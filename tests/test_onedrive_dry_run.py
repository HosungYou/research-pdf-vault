from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
RPV: Final = SCRIPTS_DIR / "rpv.py"


def test_scan_dry_run_when_onedrive_file_exists_then_records_metadata_without_hashing(
    tmp_path: Path,
) -> None:
    # Given
    source_root = tmp_path / "OneDrive-Research"
    source_root.mkdir()
    pdf_path = source_root / "public-research.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R >> endobj\n"
        b"%%EOF\n",
    )
    manifest_db = tmp_path / "cache" / "manifest.sqlite3"
    config_path = tmp_path / "rpv.toml"
    config_path.write_text(
        "\n".join(
            (
                f'storage_roots = ["{source_root}"]',
                'cache_root = "cache"',
                'manifest_db = "cache/manifest.sqlite3"',
                'ocr_engine = "none"',
                'embedding_backend = "fixture"',
                'local_llm_backend = "disabled"',
                "enable_external_models = false",
                "max_external_passage_chars = 0",
                "",
                "[sync]",
                'provider = "onedrive_local"',
                "dry_run_metadata_only = true",
                "",
            ),
        ),
        encoding="utf-8",
    )

    # When
    completed = subprocess.run(
        [
            sys.executable,
            str(RPV),
            "scan",
            "--config",
            str(config_path),
            "--once",
            "--dry-run",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert completed.returncode == 0, completed.stderr
    assert "dry_run=1" in completed.stdout
    assert "ready=0" in completed.stdout
    assert "pending=1" in completed.stdout
    with sqlite3.connect(manifest_db) as connection:
        row = connection.execute(
            "SELECT sha256, sync_status, provider_status FROM filesystem_snapshot",
        ).fetchone()
    assert row == (None, "dry_run_metadata_only", "onedrive_local")


def test_scan_dry_run_when_sync_section_is_absent_then_still_uses_metadata_only_probe(
    tmp_path: Path,
) -> None:
    # Given
    source_root = tmp_path / "library"
    source_root.mkdir()
    (source_root / "public-research.pdf").write_bytes(
        b"%PDF-1.4\n/Page\n%%EOF\n",
    )
    manifest_db = tmp_path / "cache" / "manifest.sqlite3"
    config_path = tmp_path / "rpv.toml"
    config_path.write_text(
        "\n".join(
            (
                f'storage_roots = ["{source_root}"]',
                'cache_root = "cache"',
                'manifest_db = "cache/manifest.sqlite3"',
                'ocr_engine = "none"',
                'embedding_backend = "fixture"',
                'local_llm_backend = "disabled"',
                "enable_external_models = false",
                "max_external_passage_chars = 0",
                "",
            ),
        ),
        encoding="utf-8",
    )

    # When
    completed = subprocess.run(
        [
            sys.executable,
            str(RPV),
            "scan",
            "--config",
            str(config_path),
            "--once",
            "--dry-run",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert completed.returncode == 0, completed.stderr
    assert "dry_run=1" in completed.stdout
    with sqlite3.connect(manifest_db) as connection:
        row = connection.execute(
            "SELECT sha256, sync_status, provider_status FROM filesystem_snapshot",
        ).fetchone()
    assert row == (None, "dry_run_metadata_only", "local")


def test_scan_dry_run_when_followed_by_ingest_then_does_not_duplicate_papers(
    tmp_path: Path,
) -> None:
    # Given
    source_root = tmp_path / "library"
    source_root.mkdir()
    (source_root / "public-research.pdf").write_bytes(
        b"%PDF-1.4\n/Page\n%%EOF\n",
    )
    manifest_db = tmp_path / "cache" / "manifest.sqlite3"
    config_path = tmp_path / "rpv.toml"
    config_path.write_text(
        "\n".join(
            (
                f'storage_roots = ["{source_root}"]',
                'cache_root = "cache"',
                'manifest_db = "cache/manifest.sqlite3"',
                'ocr_engine = "none"',
                'embedding_backend = "fixture"',
                'local_llm_backend = "disabled"',
                "enable_external_models = false",
                "max_external_passage_chars = 0",
                "",
            ),
        ),
        encoding="utf-8",
    )

    # When
    dry_run = subprocess.run(
        [
            sys.executable,
            str(RPV),
            "scan",
            "--config",
            str(config_path),
            "--once",
            "--dry-run",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    ingest = subprocess.run(
        [
            sys.executable,
            str(RPV),
            "ingest",
            "--config",
            str(config_path),
            "--once",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert dry_run.returncode == 0, dry_run.stderr
    assert ingest.returncode == 0, ingest.stderr
    with sqlite3.connect(manifest_db) as connection:
        paper_count = connection.execute("SELECT COUNT(*) FROM paper").fetchone()[0]
        instance_count = connection.execute(
            "SELECT COUNT(*) FROM paper_instance",
        ).fetchone()[0]
    assert paper_count == 1
    assert instance_count == 1
