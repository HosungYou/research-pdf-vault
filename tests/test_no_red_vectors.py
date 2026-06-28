from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

TEXT_PDF_BYTES: Final = (
    b"%PDF-1.4\n"
    b"%%RPV_PAGE 1\n"
    b"Synthetic paper text that would be indexed if the lane allowed it.\n"
    b"%%RPV_END_PAGE\n"
    b"%%EOF\n"
)
GAP_PDF_BYTES: Final = (
    b"%PDF-1.4\n"
    b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
    b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
    b"3 0 obj << /Type /Page /Parent 2 0 R >> endobj\n"
    b"%%EOF\n"
)


@dataclass(frozen=True, slots=True)
class SeededInstance:
    paper_id: str
    instance_id: str
    file_path: str
    lane: str
    identifiers: str


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


def rows(db_path: Path, query: str) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        return list(connection.execute(query))


def seed_instance(
    db_path: Path,
    instance: SeededInstance,
) -> None:
    from research_pdf_vault.scan_db import initialize_scan_database, now_timestamp

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        initialize_scan_database(connection)
        timestamp = now_timestamp()
        connection.execute(
            "INSERT INTO paper (schema_version, paper_id, title, normalized_identifiers, lane, created_at) "
            "VALUES ('1.0.0', ?, 'Synthetic seeded paper', ?, ?, ?)",
            (instance.paper_id, instance.identifiers, instance.lane, timestamp),
        )
        connection.execute(
            "INSERT INTO paper_instance (schema_version, instance_id, paper_id, file_path, sha256, instance_status, discovered_at) "
            "VALUES ('1.0.0', ?, ?, ?, ?, 'available', ?)",
            (
                instance.instance_id,
                instance.paper_id,
                instance.file_path,
                "a" * 64,
                timestamp,
            ),
        )


def test_index_builder_when_red_paper_has_text_then_writes_quarantine_status_only(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.config import ConfigLoadRequest, load_config
    from research_pdf_vault.index_build import build_local_index

    # Given
    library = tmp_path / "library"
    library.mkdir()
    (library / "red-text.pdf").write_bytes(TEXT_PDF_BYTES)
    config_path = tmp_path / "rpv.toml"
    write_config(config_path)
    config = load_config(ConfigLoadRequest(config_path=config_path))
    seed_instance(
        config.manifest_db,
        SeededInstance(
            paper_id="paper_red_seed",
            instance_id="instance_red_seed",
            file_path="library/red-text.pdf",
            lane="red",
            identifiers='{"source":"seed"}',
        ),
    )

    # When
    summary = build_local_index(config)

    # Then
    assert summary.quarantined_count == 1
    assert rows(config.manifest_db, "SELECT * FROM index_chunk") == []
    assert rows(config.manifest_db, "SELECT * FROM chunk_embedding") == []
    status = rows(
        config.manifest_db,
        "SELECT lane, stage_status, vector_artifact_path FROM artifact_status",
    )
    assert [dict(row) for row in status] == [
        {
            "lane": "red",
            "stage_status": "quarantined",
            "vector_artifact_path": None,
        },
    ]
    audit = rows(config.manifest_db, "SELECT action, reason FROM audit_log")
    assert [dict(row) for row in audit] == [
        {
            "action": "quarantine",
            "reason": "red lane cannot be indexed",
        },
    ]


def test_index_builder_when_gap_only_metadata_row_then_creates_no_vectors(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.config import ConfigLoadRequest, load_config
    from research_pdf_vault.index_build import build_local_index

    # Given
    library = tmp_path / "library"
    library.mkdir()
    (library / "gap-only.pdf").write_bytes(GAP_PDF_BYTES)
    config_path = tmp_path / "rpv.toml"
    write_config(config_path)
    config = load_config(ConfigLoadRequest(config_path=config_path))
    seed_instance(
        config.manifest_db,
        SeededInstance(
            paper_id="paper_gap_seed",
            instance_id="instance_gap_seed",
            file_path="library/gap-only.pdf",
            lane="green",
            identifiers='{"support_tag":"gap"}',
        ),
    )

    # When
    summary = build_local_index(config)

    # Then
    assert summary.skipped_count == 1
    assert rows(config.manifest_db, "SELECT * FROM index_chunk") == []
    assert rows(config.manifest_db, "SELECT * FROM chunk_embedding") == []
    status = rows(
        config.manifest_db,
        "SELECT lane, stage_status, vector_artifact_path FROM artifact_status",
    )
    assert [dict(row) for row in status] == [
        {
            "lane": "green",
            "stage_status": "failed",
            "vector_artifact_path": None,
        },
    ]
