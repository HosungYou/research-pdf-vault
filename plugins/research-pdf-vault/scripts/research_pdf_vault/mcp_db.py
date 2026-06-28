from __future__ import annotations

import sqlite3
from typing import assert_never

from research_pdf_vault.config import VaultRuntimeConfig
from research_pdf_vault.mcp_types import JsonObject
from research_pdf_vault.schema import Lane


def open_read_connection(config: VaultRuntimeConfig) -> sqlite3.Connection | None:
    if not config.manifest_db.exists():
        return None
    connection = sqlite3.connect(f"{config.manifest_db.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def count_table(connection: sqlite3.Connection, table_name: str) -> int:
    row = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    return int(row[0])


def like_pattern(query: str) -> str:
    return f"%{query.casefold()}%"


def review_queue_items(
    connection: sqlite3.Connection,
    limit: int,
) -> list[JsonObject]:
    rows = connection.execute(
        "SELECT q.queue_item_id, q.paper_id, p.title, q.lane, q.stage_status, q.priority, q.reason, q.created_at "
        "FROM review_queue_item q JOIN paper p ON p.paper_id = q.paper_id "
        "ORDER BY CASE q.priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, q.created_at LIMIT ?",
        (limit,),
    ).fetchall()
    return [queue_item_json(row) for row in rows]


def review_queue_rows_for_paper(
    connection: sqlite3.Connection,
    paper_id: str,
) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT q.queue_item_id, q.paper_id, p.title, q.lane, q.stage_status, q.priority, q.reason, q.created_at "
        "FROM review_queue_item q JOIN paper p ON p.paper_id = q.paper_id WHERE q.paper_id = ?",
        (paper_id,),
    ).fetchall()


def queue_item_json(row: sqlite3.Row) -> JsonObject:
    return {
        "queue_item_id": str(row[0]),
        "paper_id": str(row[1]),
        "title": str(row[2]),
        "lane": str(row[3]),
        "stage_status": str(row[4]),
        "priority": str(row[5]),
        "reason": _review_reason(row),
        "created_at": str(row[7]),
    }


def _review_reason(row: sqlite3.Row) -> str:
    lane = Lane(str(row[3]))
    match lane:
        case Lane.RED:
            return "metadata-only: red lane quarantined"
        case Lane.GREEN | Lane.AMBER:
            return str(row[6])
        case unreachable:
            assert_never(unreachable)
