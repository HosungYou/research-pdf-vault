from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

PDF_PAGES: Final = b"%%EOF\n/Page\n"


def test_scan_classification_when_default_policy_then_only_red_enters_review_queue(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.config import ConfigLoadRequest, load_config
    from research_pdf_vault.scanner import run_one_shot_scan

    # Given
    library = tmp_path / "library"
    library.mkdir()
    (library / "ambiguous-deck.pdf").write_bytes(b"%PDF-1.4\n" + PDF_PAGES)
    (library / "student-irb-notes.pdf").write_bytes(
        b"%PDF-1.4\n"
        b"%%RPV_PAGE 1\n"
        b"IRB protocol student participant consent notes.\n"
        b"%%RPV_END_PAGE\n"
        + PDF_PAGES,
    )
    config_path = tmp_path / "rpv.toml"
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
                "max_external_passage_chars = 0",
                "",
            ),
        ),
        encoding="utf-8",
    )
    config = load_config(ConfigLoadRequest(config_path=config_path))

    # When
    run_one_shot_scan(config)

    # Then
    with sqlite3.connect(config.manifest_db) as connection:
        lanes = connection.execute(
            "SELECT lane, COUNT(*) FROM paper GROUP BY lane ORDER BY lane",
        ).fetchall()
        queue_lanes = connection.execute(
            "SELECT lane, stage_status FROM review_queue_item ORDER BY lane",
        ).fetchall()
    assert lanes == [("amber", 1), ("red", 1)]
    assert queue_lanes == [("red", "quarantined")]


def test_scan_classification_when_amber_is_configured_then_amber_enters_review_queue(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.config import ConfigLoadRequest, load_config
    from research_pdf_vault.scanner import run_one_shot_scan

    # Given
    library = tmp_path / "library"
    library.mkdir()
    (library / "ambiguous-deck.pdf").write_bytes(b"%PDF-1.4\n" + PDF_PAGES)
    config_path = tmp_path / "rpv.toml"
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
                "max_external_passage_chars = 0",
                "",
                "[approval]",
                'manual_review_lanes = ["amber", "red"]',
                "",
            ),
        ),
        encoding="utf-8",
    )
    config = load_config(ConfigLoadRequest(config_path=config_path))

    # When
    run_one_shot_scan(config)

    # Then
    with sqlite3.connect(config.manifest_db) as connection:
        queue_lanes = connection.execute(
            "SELECT lane, stage_status FROM review_queue_item ORDER BY lane",
        ).fetchall()
    assert queue_lanes == [("amber", "pending")]
