from __future__ import annotations

import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
RPV: Final = SCRIPTS_DIR / "rpv.py"
sys.path.insert(0, str(SCRIPTS_DIR))


@dataclass(frozen=True, slots=True)
class CliReviewFixture:
    config_path: Path
    manifest_db: Path


@dataclass(frozen=True, slots=True)
class SeedPaper:
    paper_id: str
    lane: str
    stage_status: str
    reason: str


def test_cli_review_approve_persists_lane_review_state_and_audit(
    tmp_path: Path,
) -> None:
    # Given
    fixture = _cli_fixture(tmp_path)
    _seed_manifest(
        fixture.manifest_db,
        SeedPaper(
            paper_id="paper_cli_amber_001",
            lane="amber",
            stage_status="pending",
            reason="ambiguous source needs CLI review",
        ),
    )

    # When
    completed = subprocess.run(
        [
            sys.executable,
            str(RPV),
            "review",
            "approve",
            "--config",
            str(fixture.config_path),
            "paper_cli_amber_001",
            "--actor",
            "cli-reviewer",
            "--reason",
            "cli approved public record",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert completed.returncode == 0
    assert "review ok:" in completed.stdout
    with sqlite3.connect(fixture.manifest_db) as connection:
        assert _paper_lane(connection, "paper_cli_amber_001") == "green"
        assert _review_state(connection, "paper_cli_amber_001") == (
            "green",
            "complete",
        )
        assert _audit_rows(connection, "paper_cli_amber_001") == [
            ("release", "review approve by cli-reviewer: cli approved public record"),
        ]


def test_cli_red_refusal_persists_review_state_and_audit(tmp_path: Path) -> None:
    # Given
    fixture = _cli_fixture(tmp_path)
    _seed_manifest(
        fixture.manifest_db,
        SeedPaper(
            paper_id="paper_cli_red_001",
            lane="red",
            stage_status="quarantined",
            reason="sensitive_excerpt includes participant consent",
        ),
    )

    # When
    completed = subprocess.run(
        [
            sys.executable,
            str(RPV),
            "review",
            "approve",
            "--config",
            str(fixture.config_path),
            "paper_cli_red_001",
            "--actor",
            "cli-reviewer",
            "--reason",
            "attempted CLI release",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert completed.returncode == 1
    assert "red sensitive item requires --allow-sensitive" in completed.stderr
    with sqlite3.connect(fixture.manifest_db) as connection:
        assert _paper_lane(connection, "paper_cli_red_001") == "red"
        assert _review_state(connection, "paper_cli_red_001") == (
            "red",
            "quarantined",
        )
        assert _audit_rows(connection, "paper_cli_red_001") == [
            (
                "quarantine",
                "review approve refused by cli-reviewer: red sensitive item requires --allow-sensitive",
            ),
        ]


def _cli_fixture(tmp_path: Path) -> CliReviewFixture:
    manifest_db = tmp_path / "manifest.sqlite3"
    config_path = tmp_path / "rpv.toml"
    config_path.write_text(
        "\n".join(
            (
                'cache_root = "cache"',
                'manifest_db = "manifest.sqlite3"',
                'ocr_engine = "none"',
                'embedding_backend = "fixture"',
                'local_llm_backend = "disabled"',
                "enable_external_models = false",
                "max_external_passage_chars = 0",
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
    return CliReviewFixture(config_path=config_path, manifest_db=manifest_db)


def _seed_manifest(manifest_db: Path, seed: SeedPaper) -> None:
    from research_pdf_vault.review_queue import initialize_review_database

    with sqlite3.connect(manifest_db) as connection:
        initialize_review_database(connection)
        connection.execute(
            "INSERT INTO paper (schema_version, paper_id, title, normalized_identifiers, lane, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                seed.paper_id,
                "Synthetic CLI review paper",
                '{"source":"cli-test"}',
                seed.lane,
                "2026-01-01T00:00:00Z",
            ),
        )
        connection.execute(
            "INSERT INTO classification_decision (schema_version, decision_id, paper_id, lane, stage_status, actor, timestamp, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                f"decision_{seed.paper_id.removeprefix('paper_')}",
                seed.paper_id,
                seed.lane,
                seed.stage_status,
                "classifier",
                "2026-01-01T00:01:00Z",
                seed.reason,
            ),
        )


def _paper_lane(connection: sqlite3.Connection, paper_id: str) -> str:
    row = connection.execute(
        "SELECT lane FROM paper WHERE paper_id = ?",
        (paper_id,),
    ).fetchone()
    return str(row[0])


def _review_state(connection: sqlite3.Connection, paper_id: str) -> tuple[str, str]:
    row = connection.execute(
        "SELECT lane, stage_status FROM review_queue_item WHERE paper_id = ?",
        (paper_id,),
    ).fetchone()
    return (str(row[0]), str(row[1]))


def _audit_rows(connection: sqlite3.Connection, paper_id: str) -> list[tuple[str, str]]:
    rows = connection.execute(
        "SELECT action, reason FROM audit_log WHERE paper_id = ? ORDER BY timestamp",
        (paper_id,),
    ).fetchall()
    return [(str(action), str(reason)) for action, reason in rows]
