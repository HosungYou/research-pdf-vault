from __future__ import annotations

import hashlib
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
RPV: Final = SCRIPTS_DIR / "rpv.py"
PDF_BYTES: Final = (
    b"%PDF-1.4\n"
    b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
    b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
    b"3 0 obj << /Type /Page /Parent 2 0 R >> endobj\n"
    b"%%EOF\n"
)


def test_import_when_local_pdf_then_copies_to_inbox_and_records_event(
    tmp_path: Path,
) -> None:
    # Given
    source_pdf = tmp_path / "Technology Acceptance Model.pdf"
    source_pdf.write_bytes(PDF_BYTES)
    storage_root = tmp_path / "storage"
    cache_root = tmp_path / "cache"
    config_path = tmp_path / "rpv.toml"
    config_path.write_text(
        _config_text(storage_root=storage_root, cache_root=cache_root),
        encoding="utf-8",
    )
    sha256 = hashlib.sha256(PDF_BYTES).hexdigest()
    expected_name = f"{sha256}-technology-acceptance-model.pdf"

    # When
    imported = _run_rpv(
        "import",
        str(source_pdf),
        "--config",
        str(config_path),
        "--doi",
        "10.0000/example.import",
        "--source",
        "manual-test",
    )
    ingest = _run_rpv("ingest", "--once", "--config", str(config_path))

    # Then
    assert imported.returncode == 0, imported.stderr
    assert f"import ok: status=imported sha256={sha256}" in imported.stdout
    assert f"relative_path={storage_root.name}/inbox/{expected_name}" in imported.stdout
    assert (storage_root / "inbox" / expected_name).read_bytes() == PDF_BYTES
    assert source_pdf.exists()

    assert ingest.returncode == 0, ingest.stderr
    assert "ingest ok: scanned=1 ready=1 pending=0" in ingest.stdout
    assert _import_event_count(cache_root / "manifest.sqlite3", sha256) == 1


def test_import_when_same_pdf_imported_twice_then_reuses_existing_inbox_file(
    tmp_path: Path,
) -> None:
    # Given
    source_pdf = tmp_path / "Duplicate Study.pdf"
    source_pdf.write_bytes(PDF_BYTES)
    storage_root = tmp_path / "storage"
    cache_root = tmp_path / "cache"
    config_path = tmp_path / "rpv.toml"
    config_path.write_text(
        _config_text(storage_root=storage_root, cache_root=cache_root),
        encoding="utf-8",
    )
    sha256 = hashlib.sha256(PDF_BYTES).hexdigest()

    # When
    first = _run_rpv("import", str(source_pdf), "--config", str(config_path))
    second = _run_rpv("import", str(source_pdf), "--config", str(config_path))

    # Then
    assert first.returncode == 0, first.stderr
    assert "status=imported" in first.stdout
    assert second.returncode == 0, second.stderr
    assert "status=existing" in second.stdout
    assert len(tuple((storage_root / "inbox").glob("*.pdf"))) == 1
    assert _import_event_count(cache_root / "manifest.sqlite3", sha256) == 2


def _config_text(storage_root: Path, cache_root: Path) -> str:
    return "\n".join(
        (
            f'storage_roots = ["{storage_root}"]',
            f'cache_root = "{cache_root}"',
            f'manifest_db = "{cache_root}/manifest.sqlite3"',
            'ocr_engine = "none"',
            'embedding_backend = "fixture"',
            'local_llm_backend = "disabled"',
            "enable_external_models = false",
            "max_external_passage_chars = 1200",
            "",
            "[sync]",
            'provider = "local"',
            "dry_run_metadata_only = false",
            "",
            "[approval]",
            'manual_review_lanes = ["red"]',
            "",
            "[notifications]",
            "discord_enabled = false",
            'discord_webhook_env = "RPV_DISCORD_WEBHOOK"',
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
    )


def _run_rpv(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RPV), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _import_event_count(manifest_db: Path, sha256: str) -> int:
    with sqlite3.connect(manifest_db) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM import_event WHERE sha256 = ?",
            (sha256,),
        ).fetchone()
    return int(row[0])
