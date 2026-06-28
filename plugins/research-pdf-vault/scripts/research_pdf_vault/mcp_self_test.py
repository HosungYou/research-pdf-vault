from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory

from research_pdf_vault.config import ConfigLoadRequest, load_config
from research_pdf_vault.mcp_tools import McpToolRunner
from research_pdf_vault.mcp_types import JsonObject
from research_pdf_vault.review_queue import initialize_review_database


@dataclass(frozen=True, slots=True)
class SelfTestPaper:
    paper_id: str
    title: str
    lane: str
    stage_status: str
    priority: str
    reason: str
    passage: str = ""


def build_self_test_payload(config_path: Path | None) -> JsonObject:
    config = load_config(ConfigLoadRequest(config_path=config_path))
    with TemporaryDirectory(prefix="rpv-mcp-self-test-") as temp_dir:
        manifest_db = Path(temp_dir) / "manifest.sqlite3"
        _seed_manifest(manifest_db)
        runner = McpToolRunner(replace(config, manifest_db=manifest_db))
        return {
            "manifest_summary": runner.call_tool("get_manifest_summary", {}),
            "review_queue": runner.call_tool("list_review_queue", {}),
            "search": runner.call_tool("search_papers", {"query": "learning"}),
            "red_full_text_request": runner.call_tool(
                "get_paper",
                {"paper_id": "paper_selftest_red_001", "include_full_text": True},
            ),
            "reports": runner.call_tool("list_reports", {}),
        }


def _seed_manifest(manifest_db: Path) -> None:
    seeds = (
        SelfTestPaper(
            "paper_selftest_green_001",
            "Learning gains in public tutoring study",
            "green",
            "complete",
            "low",
            "public article",
            "Learning gains improved after local tutoring intervention.",
        ),
        SelfTestPaper(
            "paper_selftest_amber_001",
            "Ambiguous workshop deck",
            "amber",
            "pending",
            "normal",
            "needs reviewer decision",
        ),
        SelfTestPaper(
            "paper_selftest_red_001",
            "Sensitive participant notes",
            "red",
            "quarantined",
            "high",
            "participant notes are quarantined",
            "participant private note must stay local",
        ),
    )
    with sqlite3.connect(manifest_db) as connection:
        initialize_review_database(connection)
        for seed in seeds:
            _insert_paper(connection, seed)
            if seed.lane != "green":
                _insert_queue(connection, seed)
            if seed.passage:
                _insert_passage(connection, seed)
        _insert_report(connection)


def _insert_paper(connection: sqlite3.Connection, seed: SelfTestPaper) -> None:
    connection.execute(
        "INSERT INTO paper (schema_version, paper_id, title, normalized_identifiers, lane, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("1.0.0", seed.paper_id, seed.title, '{"source":"mcp-self-test"}', seed.lane, "2026-01-01T00:00:00Z"),
    )
    connection.execute(
        "INSERT INTO classification_decision (schema_version, decision_id, paper_id, lane, stage_status, actor, timestamp, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("1.0.0", f"decision_{seed.paper_id.removeprefix('paper_')}", seed.paper_id, seed.lane, seed.stage_status, "self-test", "2026-01-01T00:01:00Z", seed.reason),
    )


def _insert_queue(connection: sqlite3.Connection, seed: SelfTestPaper) -> None:
    connection.execute(
        "INSERT INTO review_queue_item (schema_version, queue_item_id, paper_id, lane, stage_status, priority, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("1.0.0", f"queue_{seed.paper_id.removeprefix('paper_')}", seed.paper_id, seed.lane, seed.stage_status, seed.priority, seed.reason, "2026-01-01T00:02:00Z"),
    )


def _insert_passage(connection: sqlite3.Connection, seed: SelfTestPaper) -> None:
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
        ("1.0.0", "report_selftest_001", "mcp-self-test", "paper_selftest_green_001", "complete", "2026-01-01T00:03:00Z", "2026-01-01T00:04:00Z", "sha256:" + "b" * 64, "Synthetic MCP self-test completed"),
    )
