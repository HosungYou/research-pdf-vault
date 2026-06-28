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


def test_notify_discord_dry_run_when_red_queue_exists_then_payload_is_privacy_safe(
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
    _seed_red_review_item(manifest_db)

    # When
    completed = subprocess.run(
        [
            sys.executable,
            str(RPV),
            "notify",
            "discord",
            "--config",
            str(config_path),
            "--event",
            "review-queue",
            "--dry-run",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    payload_text = json.dumps(payload)
    assert payload["username"] == "Research PDF Vault"
    assert "Red review needed: 1" in payload["content"]
    assert "rpv review list" in payload_text
    assert "Sensitive IRB Notes" not in payload_text
    assert "paper_red_sensitive_001" not in payload_text


def _seed_red_review_item(manifest_db: Path) -> None:
    from research_pdf_vault.review_queue import initialize_review_database

    manifest_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(manifest_db) as connection:
        initialize_review_database(connection)
        connection.execute(
            "INSERT INTO paper (schema_version, paper_id, title, normalized_identifiers, lane, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "paper_red_sensitive_001",
                "Sensitive IRB Notes",
                '{"source":"discord-test"}',
                "red",
                "2026-01-01T00:00:00Z",
            ),
        )
        connection.execute(
            "INSERT INTO review_queue_item (schema_version, queue_item_id, paper_id, lane, stage_status, priority, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "queue_red_sensitive_001",
                "paper_red_sensitive_001",
                "red",
                "quarantined",
                "high",
                "sensitive participant excerpt",
                "2026-01-01T00:01:00Z",
            ),
        )
