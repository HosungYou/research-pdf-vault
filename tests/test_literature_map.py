from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
RPV: Final = SCRIPTS_DIR / "rpv.py"
sys.path.insert(0, str(SCRIPTS_DIR))


def test_literature_map_build_when_claim_cards_exist_then_creates_graph_summary(
    tmp_path: Path,
) -> None:
    # Given
    manifest_db = tmp_path / "cache" / "manifest.sqlite3"
    config_path = tmp_path / "rpv.toml"
    config_path.write_text(
        "\n".join(
            (
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
    _seed_claim_card(manifest_db)

    # When
    build = subprocess.run(
        [
            sys.executable,
            str(RPV),
            "literature-map",
            "build",
            "--config",
            str(config_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    report = subprocess.run(
        [
            sys.executable,
            str(RPV),
            "literature-map",
            "report",
            "--config",
            str(config_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert build.returncode == 0, build.stderr
    assert "nodes=2" in build.stdout
    assert "edges=1" in build.stdout
    assert report.returncode == 0, report.stderr
    payload = json.loads(report.stdout)
    assert payload["node_counts"] == {"claim": 1, "paper": 1}
    assert payload["edge_counts"] == {"supports_claim": 1}
    assert payload["graph_focus"] == "literature_map"


def _seed_claim_card(manifest_db: Path) -> None:
    from research_pdf_vault.db import initialize_database

    manifest_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(manifest_db) as connection:
        initialize_database(connection)
        connection.execute(
            "INSERT INTO paper (schema_version, paper_id, title, normalized_identifiers, lane, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "paper_litmap_001",
                "Public Learning Gains Study",
                '{"source":"literature-map-test"}',
                "green",
                "2026-01-01T00:00:00Z",
            ),
        )
        connection.execute(
            "INSERT INTO paper_instance (schema_version, instance_id, paper_id, file_path, sha256, instance_status, discovered_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "instance_litmap_001",
                "paper_litmap_001",
                "library/learning-gains.pdf",
                "a" * 64,
                "available",
                "2026-01-01T00:00:01Z",
            ),
        )
        connection.execute(
            "INSERT INTO extracted_passage (schema_version, passage_id, paper_id, instance_id, source_page, start_offset, end_offset, text, support_tag) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "passage_litmap_001",
                "paper_litmap_001",
                "instance_litmap_001",
                4,
                0,
                18,
                "AI tutoring improved test scores.",
                "supports",
            ),
        )
        connection.execute(
            "INSERT INTO claim_card (schema_version, claim_id, paper_id, passage_id, claim_text, support_tag, source_page, start_offset, end_offset) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "claim_litmap_001",
                "paper_litmap_001",
                "passage_litmap_001",
                "AI tutoring improved test scores.",
                "supports",
                4,
                0,
                18,
            ),
        )
