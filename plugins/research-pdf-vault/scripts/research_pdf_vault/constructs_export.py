from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from research_pdf_vault.config import VaultRuntimeConfig
from research_pdf_vault.constructs import initialize_construct_tables
from research_pdf_vault.db import initialize_database
from research_pdf_vault.mcp_types import JsonObject


@dataclass(frozen=True, slots=True)
class ConstructExportResult:
    jsonl_path: Path
    markdown_path: Path
    registry_count: int
    candidate_count: int


def export_construct_registry(config: VaultRuntimeConfig) -> ConstructExportResult:
    export_dir = config.cache_root / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = export_dir / "construct_registry.jsonl"
    markdown_path = export_dir / "construct_registry.md"
    with sqlite3.connect(config.manifest_db) as connection:
        initialize_database(connection)
        initialize_construct_tables(connection)
        rows = _registry_export_rows(connection)
    jsonl_path.write_text(_jsonl_text(rows), encoding="utf-8")
    markdown_path.write_text(_markdown_text(rows), encoding="utf-8")
    return ConstructExportResult(
        jsonl_path=jsonl_path,
        markdown_path=markdown_path,
        registry_count=len(rows),
        candidate_count=sum(len(row["candidates"]) for row in rows),
    )


def _registry_export_rows(connection: sqlite3.Connection) -> list[JsonObject]:
    rows = connection.execute(
        "SELECT construct_id, canonical_label, aliases_json, definition_notes, measurement_families_json, theory_links_json, merge_status, review_status "
        "FROM construct_registry ORDER BY canonical_label",
    )
    return [
        {
            "construct_id": str(construct_id),
            "canonical_label": str(canonical_label),
            "aliases": json.loads(str(aliases_json)),
            "definition_notes": str(definition_notes),
            "measurement_families": json.loads(str(measurement_families_json)),
            "theory_links": json.loads(str(theory_links_json)),
            "merge_status": str(merge_status),
            "review_status": str(review_status),
            "candidates": _candidate_export_rows(connection, str(construct_id)),
        }
        for (
            construct_id,
            canonical_label,
            aliases_json,
            definition_notes,
            measurement_families_json,
            theory_links_json,
            merge_status,
            review_status,
        ) in rows
    ]


def _candidate_export_rows(
    connection: sqlite3.Connection,
    construct_id: str,
) -> list[JsonObject]:
    rows = connection.execute(
        "SELECT candidate_id, paper_id, reported_term, candidate_normalization, measurement_proxy, theoretical_role, confidence, review_required, source_page "
        "FROM construct_candidate WHERE construct_id = ? ORDER BY reported_term, paper_id",
        (construct_id,),
    )
    return [
        {
            "candidate_id": str(candidate_id),
            "paper_id": str(paper_id),
            "reported_term": str(reported_term),
            "candidate_normalization": str(candidate_normalization),
            "measurement_proxy": str(measurement_proxy),
            "theoretical_role": str(theoretical_role),
            "confidence": float(confidence),
            "review_required": bool(review_required),
            "source_page": int(source_page),
        }
        for (
            candidate_id,
            paper_id,
            reported_term,
            candidate_normalization,
            measurement_proxy,
            theoretical_role,
            confidence,
            review_required,
            source_page,
        ) in rows
    ]


def _jsonl_text(rows: list[JsonObject]) -> str:
    return "".join(f"{json.dumps(row, sort_keys=True)}\n" for row in rows)


def _markdown_text(rows: list[JsonObject]) -> str:
    lines = ["# Construct Registry", ""]
    for row in rows:
        lines.extend(_registry_markdown_block(row))
    return "\n".join(lines)


def _registry_markdown_block(row: JsonObject) -> list[str]:
    lines = [
        f"## {row['canonical_label']}",
        "",
        f"- Construct ID: `{row['construct_id']}`",
        f"- Merge status: `{row['merge_status']}`",
        f"- Review status: `{row['review_status']}`",
        f"- Aliases: {_join_items(row['aliases'])}",
        f"- Measurement families: {_join_items(row['measurement_families'])}",
        "",
        "| Reported term | Measurement proxy | Role | Confidence | Review | Paper | Page |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    candidates = row["candidates"]
    if isinstance(candidates, list):
        for candidate in candidates:
            lines.append(_candidate_markdown_row(candidate))
    lines.append("")
    return lines


def _candidate_markdown_row(candidate: JsonObject) -> str:
    return (
        "| "
        f"{candidate['reported_term']} | "
        f"{candidate['measurement_proxy']} | "
        f"{candidate['theoretical_role']} | "
        f"{float(candidate['confidence']):.2f} | "
        f"{candidate['review_required']} | "
        f"`{candidate['paper_id']}` | "
        f"{candidate['source_page']} |"
    )


def _join_items(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)
