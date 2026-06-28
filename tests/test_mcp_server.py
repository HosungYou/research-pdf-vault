from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
MCP_SERVER: Final = SCRIPTS_DIR / "mcp_server.py"
SAMPLE_CONFIG: Final = ROOT / "fixtures" / "config" / "sample-config.toml"
sys.path.insert(0, str(SCRIPTS_DIR))


@dataclass(frozen=True, slots=True)
class McpFixture:
    config_path: Path
    manifest_db: Path


@dataclass(frozen=True, slots=True)
class SeedPaper:
    paper_id: str
    title: str
    lane: str
    stage_status: str
    reason: str
    passage: str = ""


def test_self_test_when_sample_config_then_lists_manifest_and_review_queue() -> None:
    # Given
    command = [
        sys.executable,
        str(MCP_SERVER),
        "--self-test",
        "--config",
        str(SAMPLE_CONFIG),
    ]

    # When
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["manifest_summary"]["counts"]["papers"] == 3
    assert [item["paper_id"] for item in payload["review_queue"]["items"]] == [
        "paper_selftest_red_001",
        "paper_selftest_amber_001",
    ]
    assert payload["search"]["results"][0]["snippets"]


def test_read_tools_when_red_text_requested_then_return_metadata_only(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.mcp_tools import McpToolRunner

    # Given
    fixture = _seeded_fixture(tmp_path)
    runner = McpToolRunner.from_config_path(fixture.config_path)

    # When
    search = runner.call_tool("search_papers", {"query": "participant", "limit": 5})
    paper = runner.call_tool(
        "get_paper",
        {"paper_id": "paper_mcp_red_001", "include_full_text": True},
    )

    # Then
    red = _result_for(search["results"], "paper_mcp_red_001")
    assert red["metadata_only"] is True
    assert red["quarantine_status"] == "quarantined"
    assert red["snippets"] == []
    assert paper["full_text_status"] == "metadata_only"
    assert paper["quarantine_status"] == "quarantined"
    assert paper["passages"] == []
    assert "participant interview secret" not in json.dumps([search, paper])


def test_mutation_and_reports_when_fixture_loaded_then_scope_is_review_audit_only(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.mcp_tools import McpToolRunner

    # Given
    fixture = _seeded_fixture(tmp_path)
    runner = McpToolRunner.from_config_path(fixture.config_path)

    # When
    mutation = runner.call_tool(
        "apply_review_decision",
        {
            "identifier": "paper_mcp_amber_001",
            "decision": "approve",
            "actor": "mcp-reviewer",
            "reason": "approved metadata-only public source",
            "timestamp": "2026-01-01T00:15:00Z",
        },
    )
    reports = runner.call_tool("list_reports", {})
    report = runner.call_tool("get_report", {"report_id": "report_mcp_001"})

    # Then
    assert mutation["status"] == "applied"
    assert reports["reports"][0]["report_id"] == "report_mcp_001"
    assert report["report"]["summary"] == "Local indexing fixture completed"
    with sqlite3.connect(fixture.manifest_db) as connection:
        assert _paper_lane(connection, "paper_mcp_amber_001") == "amber"
        assert _review_state(connection, "paper_mcp_amber_001") == (
            "green",
            "complete",
            "approved metadata-only public source",
        )
        assert _audit_rows(connection, "paper_mcp_amber_001") == [
            (
                "release",
                "mcp approve by mcp-reviewer: approved metadata-only public source",
            ),
        ]
        assert _count(connection, "classification_decision") == 3
        assert _count(connection, "extracted_passage") == 2


def test_protocol_when_tools_call_received_then_returns_json_rpc_result(
    tmp_path: Path,
) -> None:
    # Given
    fixture = _seeded_fixture(tmp_path)
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "get_manifest_summary", "arguments": {}},
    }

    # When
    completed = subprocess.run(
        [sys.executable, str(MCP_SERVER), "--config", str(fixture.config_path)],
        input=json.dumps(request) + "\n",
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert completed.returncode == 0, completed.stderr
    response = json.loads(completed.stdout)
    assert response["id"] == 1
    assert response["result"]["counts"]["papers"] == 3


def test_limit_arguments_when_outside_schema_range_then_rejected(tmp_path: Path) -> None:
    from research_pdf_vault.mcp_tools import McpToolRunner
    from research_pdf_vault.mcp_types import McpToolError

    # Given
    runner = McpToolRunner.from_config_path(_seeded_fixture(tmp_path).config_path)

    # When / Then
    for tool_name, arguments in (
        ("search_papers", {"query": "mcp-test"}),
        ("list_review_queue", {}),
    ):
        for limit in (-1, 0, 51):
            with pytest.raises(McpToolError, match="limit"):
                runner.call_tool(tool_name, arguments | {"limit": limit})


def test_mcp_source_when_scanned_then_does_not_import_long_job_modules() -> None:
    # Given
    source_paths = (
        SCRIPTS_DIR / "mcp_server.py",
        *(SCRIPTS_DIR / "research_pdf_vault").glob("mcp_*.py"),
        SCRIPTS_DIR / "research_pdf_vault" / "reports.py",
    )
    forbidden_imports = (
        "from research_pdf_vault.index_build",
        "from research_pdf_vault.scanner",
        "from research_pdf_vault.extraction",
        "from research_pdf_vault.ocr",
        "from research_pdf_vault.vector_store",
    )

    # When
    combined_source = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)

    # Then
    for marker in forbidden_imports:
        assert marker not in combined_source


def _seeded_fixture(tmp_path: Path) -> McpFixture:
    fixture = _mcp_fixture(tmp_path)
    _seed_manifest(fixture.manifest_db)
    return fixture


def _mcp_fixture(tmp_path: Path) -> McpFixture:
    config_path = tmp_path / "rpv.toml"
    manifest_db = tmp_path / "manifest.sqlite3"
    config_path.write_text(
        (
            'cache_root = "cache"\nmanifest_db = "manifest.sqlite3"\n'
            'ocr_engine = "none"\nembedding_backend = "fixture"\n'
            'local_llm_backend = "disabled"\nenable_external_models = false\n'
            'max_external_passage_chars = 0\n\n[privacy]\n'
            'allow_cloud_cache = false\nred_lane_metadata_only = true\n'
            'allow_external_pdf_upload = false\n'
        ),
        encoding="utf-8",
    )
    return McpFixture(config_path=config_path, manifest_db=manifest_db)


def _seed_manifest(manifest_db: Path) -> None:
    from research_pdf_vault.review_queue import initialize_review_database

    seeds = (
        SeedPaper("paper_mcp_green_001", "Green tutoring study", "green", "complete", "public article", "AI tutoring improved learning outcomes in a classroom study."),
        SeedPaper("paper_mcp_amber_001", "Amber workshop deck", "amber", "pending", "needs source review"),
        SeedPaper("paper_mcp_red_001", "Red participant notes", "red", "quarantined", "participant interview secret", "participant interview secret must never leave quarantine"),
    )
    with sqlite3.connect(manifest_db) as connection:
        initialize_review_database(connection)
        for seed in seeds:
            _insert_paper(connection, seed)
        _insert_queue(connection, seeds[1])
        _insert_queue(connection, seeds[2])
        for seed in seeds:
            if seed.passage:
                _insert_passage(connection, seed)
        _insert_report(connection)


def _insert_paper(connection: sqlite3.Connection, seed: SeedPaper) -> None:
    connection.execute(
        "INSERT INTO paper (schema_version, paper_id, title, normalized_identifiers, lane, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("1.0.0", seed.paper_id, seed.title, '{"source":"mcp-test"}', seed.lane, "2026-01-01T00:00:00Z"),
    )
    connection.execute(
        "INSERT INTO classification_decision (schema_version, decision_id, paper_id, lane, stage_status, actor, timestamp, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("1.0.0", f"decision_{seed.paper_id.removeprefix('paper_')}", seed.paper_id, seed.lane, seed.stage_status, "classifier", "2026-01-01T00:01:00Z", seed.reason),
    )


def _insert_queue(connection: sqlite3.Connection, seed: SeedPaper) -> None:
    priority = "high" if seed.lane == "red" else "normal"
    connection.execute(
        "INSERT INTO review_queue_item (schema_version, queue_item_id, paper_id, lane, stage_status, priority, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("1.0.0", f"queue_{seed.paper_id.removeprefix('paper_')}", seed.paper_id, seed.lane, seed.stage_status, priority, seed.reason, "2026-01-01T00:02:00Z"),
    )


def _insert_passage(connection: sqlite3.Connection, seed: SeedPaper) -> None:
    instance_id = f"instance_{seed.paper_id.removeprefix('paper_')}"
    connection.execute(
        "INSERT INTO paper_instance (schema_version, instance_id, paper_id, file_path, sha256, instance_status, discovered_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("1.0.0", instance_id, seed.paper_id, f"library/{seed.paper_id}.pdf", None, "available", "2026-01-01T00:00:00Z"),
    )
    connection.execute(
        "INSERT INTO extracted_passage (schema_version, passage_id, paper_id, instance_id, source_page, start_offset, end_offset, text, support_tag) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("1.0.0", f"passage_{seed.paper_id.removeprefix('paper_')}", seed.paper_id, instance_id, 1, 0, len(seed.passage), seed.passage, "context"),
    )


def _insert_report(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO worker_report (schema_version, report_id, worker_name, paper_id, stage_status, started_at, finished_at, artifact_digest, summary) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("1.0.0", "report_mcp_001", "fixture-worker", "paper_mcp_green_001", "complete", "2026-01-01T00:03:00Z", "2026-01-01T00:04:00Z", "sha256:" + "a" * 64, "Local indexing fixture completed"),
    )


def _result_for(results: list[dict[str, str]], paper_id: str) -> dict[str, str]:
    matches = [result for result in results if result["paper_id"] == paper_id]
    assert len(matches) == 1
    return matches[0]


def _paper_lane(connection: sqlite3.Connection, paper_id: str) -> str:
    return str(connection.execute("SELECT lane FROM paper WHERE paper_id = ?", (paper_id,)).fetchone()[0])


def _review_state(connection: sqlite3.Connection, paper_id: str) -> tuple[str, str, str]:
    row = connection.execute(
        "SELECT lane, stage_status, reason FROM review_queue_item WHERE paper_id = ?",
        (paper_id,),
    ).fetchone()
    return (str(row[0]), str(row[1]), str(row[2]))


def _audit_rows(connection: sqlite3.Connection, paper_id: str) -> list[tuple[str, str]]:
    rows = connection.execute(
        "SELECT action, reason FROM audit_log WHERE paper_id = ? ORDER BY timestamp",
        (paper_id,),
    ).fetchall()
    return [(str(action), str(reason)) for action, reason in rows]


def _count(connection: sqlite3.Connection, table_name: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
