from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
RPV_SCRIPT: Final = SCRIPTS_DIR / "rpv.py"
sys.path.insert(0, str(SCRIPTS_DIR))

TEXT_PDF_BYTES: Final = (
    b"%PDF-1.4\n"
    b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
    b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
    b"3 0 obj << /Type /Page /Parent 2 0 R >> endobj\n"
    b"%%RPV_PAGE 1\n"
    b"Synthetic indexable research article.\n"
    b"Methods describe local retrieval and vector search.\n"
    b"%%RPV_END_PAGE\n"
    b"%%RPV_PAGE 2\n"
    b"Results describe stable artifact digests.\n"
    b"%%RPV_END_PAGE\n"
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


def run_ingest(config_path: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPTS_DIR)
    return subprocess.run(
        [
            sys.executable,
            str(RPV_SCRIPT),
            "ingest",
            "--config",
            str(config_path),
            "--once",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def rows(db_path: Path, query: str) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        return list(connection.execute(query))


def test_ingest_when_green_text_pdf_then_builds_chunks_fts_vectors_and_status(
    tmp_path: Path,
) -> None:
    # Given
    library = tmp_path / "library"
    library.mkdir()
    (library / "green-text.pdf").write_bytes(TEXT_PDF_BYTES)
    config_path = tmp_path / "rpv.toml"
    write_config(config_path)
    db_path = tmp_path / "cache" / "manifest.sqlite3"

    # When
    result = run_ingest(config_path)

    # Then
    assert result.returncode == 0, result.stderr
    assert "index ok:" in result.stdout
    chunk_rows = rows(
        db_path,
        "SELECT paper_id, source_page, text FROM index_chunk ORDER BY source_page",
    )
    assert len(chunk_rows) == 2
    assert chunk_rows[0]["source_page"] == 1
    assert "local retrieval" in chunk_rows[0]["text"]
    fts_rows = rows(
        db_path,
        "SELECT chunk_id FROM chunk_fts WHERE chunk_fts MATCH 'retrieval'",
    )
    assert len(fts_rows) == 1
    vector_rows = rows(
        db_path,
        "SELECT embedding_backend, vector_json FROM chunk_embedding",
    )
    assert [row["embedding_backend"] for row in vector_rows] == ["fixture", "fixture"]
    assert all(row["vector_json"].startswith("[") for row in vector_rows)
    status_rows = rows(
        db_path,
        "SELECT artifact_kind, lane, stage_status, artifact_digest, vector_artifact_path "
        "FROM artifact_status WHERE artifact_kind = 'vector_index'",
    )
    assert [dict(row) for row in status_rows] == [
        {
            "artifact_kind": "vector_index",
            "lane": "green",
            "stage_status": "complete",
            "artifact_digest": status_rows[0]["artifact_digest"],
            "vector_artifact_path": "index/chunk_embedding",
        },
    ]
    assert status_rows[0]["artifact_digest"].startswith("sha256:")


def test_ingest_when_repeated_then_keeps_chunks_vectors_and_digests_idempotent(
    tmp_path: Path,
) -> None:
    # Given
    library = tmp_path / "library"
    library.mkdir()
    (library / "green-text.pdf").write_bytes(TEXT_PDF_BYTES)
    config_path = tmp_path / "rpv.toml"
    write_config(config_path)
    db_path = tmp_path / "cache" / "manifest.sqlite3"

    # When
    first = run_ingest(config_path)
    assert first.returncode == 0, first.stderr
    first_digest = rows(
        db_path,
        "SELECT artifact_digest FROM artifact_status WHERE artifact_kind = 'vector_index'",
    )[0]["artifact_digest"]
    second = run_ingest(config_path)

    # Then
    assert second.returncode == 0, second.stderr
    assert rows(db_path, "SELECT COUNT(*) AS count FROM index_chunk")[0]["count"] == 2
    assert rows(db_path, "SELECT COUNT(*) AS count FROM chunk_embedding")[0]["count"] == 2
    second_digest = rows(
        db_path,
        "SELECT artifact_digest FROM artifact_status WHERE artifact_kind = 'vector_index'",
    )[0]["artifact_digest"]
    assert second_digest == first_digest
