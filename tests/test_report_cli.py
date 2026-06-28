from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from shutil import rmtree
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
RPV: Final = SCRIPTS_DIR / "rpv.py"
MCP_SERVER: Final = SCRIPTS_DIR / "mcp_server.py"
SAMPLE_CONFIG: Final = ROOT / "fixtures" / "config" / "sample-config.toml"
sys.path.insert(0, str(SCRIPTS_DIR))


@dataclass(frozen=True, slots=True)
class CliReportFixture:
    config_path: Path
    manifest_db: Path


def test_cli_report_when_manifest_exists_then_prints_public_summary(
    tmp_path: Path,
) -> None:
    # Given
    fixture = _cli_fixture(tmp_path)
    _seed_manifest(fixture.manifest_db)

    # When
    completed = subprocess.run(
        [
            sys.executable,
            str(RPV),
            "report",
            "--config",
            str(fixture.config_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["counts"] == {
        "papers": 1,
        "instances": 0,
        "review_queue_items": 1,
        "reports": 0,
    }
    assert payload["lanes"] == {"green": 0, "amber": 1, "red": 0}
    assert payload["review_queue"] == {"pending": 1}
    assert payload["privacy"]["red_lane_metadata_only"] is True
    assert payload["long_running_jobs"] == "not_triggered"


def test_cli_entrypoints_when_run_directly_then_do_not_write_repo_bytecode() -> None:
    # Given
    _remove_repo_bytecode()

    # When
    for command in (
        [
            sys.executable,
            str(RPV),
            "report",
            "--config",
            str(SAMPLE_CONFIG),
        ],
        [
            sys.executable,
            str(MCP_SERVER),
            "--self-test",
            "--config",
            str(SAMPLE_CONFIG),
        ],
    ):
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr

    # Then
    assert _repo_bytecode_paths() == ()


def _cli_fixture(tmp_path: Path) -> CliReportFixture:
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
    return CliReportFixture(config_path=config_path, manifest_db=manifest_db)


def _seed_manifest(manifest_db: Path) -> None:
    from research_pdf_vault.review_queue import initialize_review_database

    with sqlite3.connect(manifest_db) as connection:
        initialize_review_database(connection)
        connection.execute(
            "INSERT INTO paper (schema_version, paper_id, title, normalized_identifiers, lane, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "paper_report_amber_001",
                "Synthetic report CLI paper",
                '{"source":"report-cli-test"}',
                "amber",
                "2026-01-01T00:00:00Z",
            ),
        )
        connection.execute(
            "INSERT INTO review_queue_item (schema_version, queue_item_id, paper_id, lane, stage_status, priority, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "queue_report_amber_001",
                "paper_report_amber_001",
                "amber",
                "pending",
                "normal",
                "needs source review",
                "2026-01-01T00:01:00Z",
            ),
        )


def _repo_bytecode_paths() -> tuple[Path, ...]:
    package_dir = SCRIPTS_DIR / "research_pdf_vault"
    return tuple(
        path
        for path in sorted(package_dir.rglob("*"))
        if path.name == "__pycache__" or path.suffix == ".pyc"
    )


def _remove_repo_bytecode() -> None:
    cache_dir = SCRIPTS_DIR / "research_pdf_vault" / "__pycache__"
    if cache_dir.exists():
        rmtree(cache_dir)
