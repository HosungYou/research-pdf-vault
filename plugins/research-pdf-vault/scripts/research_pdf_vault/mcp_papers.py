from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from typing import Final, assert_never

from research_pdf_vault.config import VaultRuntimeConfig
from research_pdf_vault.mcp_db import (
    like_pattern,
    open_read_connection,
    queue_item_json,
    review_queue_rows_for_paper,
)
from research_pdf_vault.mcp_types import (
    IntArgSpec,
    JsonObject,
    bool_arg,
    bounded_int_arg,
    string_arg,
)
from research_pdf_vault.schema import Lane

MAX_SEARCH_LIMIT: Final = 50
SEARCH_LIMIT_ARG: Final = IntArgSpec("limit", 10, 1, MAX_SEARCH_LIMIT)


@dataclass(frozen=True, slots=True)
class SearchResultRequest:
    connection: sqlite3.Connection
    row: sqlite3.Row
    query: str


@dataclass(frozen=True, slots=True)
class PassageRequest:
    connection: sqlite3.Connection
    paper_id: str
    lane: Lane
    include_full_text: bool


@dataclass(frozen=True, slots=True)
class SnippetRequest:
    connection: sqlite3.Connection
    paper_id: str
    query: str
    lane: Lane


def search_papers(config: VaultRuntimeConfig, arguments: JsonObject) -> JsonObject:
    query = string_arg(arguments, "query")
    limit = bounded_int_arg(arguments, SEARCH_LIMIT_ARG)
    connection = open_read_connection(config)
    if connection is None:
        return {"query": query, "results": []}
    with closing(connection):
        rows = connection.execute(
            "SELECT DISTINCT p.paper_id, p.title, p.lane, p.normalized_identifiers, COALESCE(q.stage_status, '') "
            "FROM paper p LEFT JOIN review_queue_item q ON q.paper_id = p.paper_id "
            "LEFT JOIN extracted_passage e ON e.paper_id = p.paper_id "
            "WHERE lower(p.title) LIKE ? OR lower(p.normalized_identifiers) LIKE ? "
            "OR (p.lane != 'red' AND lower(e.text) LIKE ?) "
            "ORDER BY p.paper_id LIMIT ?",
            (like_pattern(query), like_pattern(query), like_pattern(query), limit),
        ).fetchall()
        return {
            "query": query,
            "results": [
                _search_result(SearchResultRequest(connection, row, query))
                for row in rows
            ],
        }


def get_paper(config: VaultRuntimeConfig, arguments: JsonObject) -> JsonObject:
    paper_id = string_arg(arguments, "paper_id")
    include_full_text = bool_arg(arguments, "include_full_text", False)
    connection = open_read_connection(config)
    if connection is None:
        return {"status": "missing", "paper_id": paper_id}
    with closing(connection):
        row = connection.execute(
            "SELECT paper_id, title, lane, normalized_identifiers, created_at FROM paper WHERE paper_id = ?",
            (paper_id,),
        ).fetchone()
        if row is None:
            return {"status": "missing", "paper_id": paper_id}
        lane = Lane(str(row["lane"]))
        passages = _paper_passages(
            PassageRequest(connection, paper_id, lane, include_full_text),
        )
        return {
            "status": "ok",
            "paper": _paper_json(row),
            "instances": _instances(connection, paper_id),
            "review": _review_json(connection, paper_id),
            "artifacts": _artifacts(connection, paper_id),
            "quarantine_status": _quarantine_status(
                lane,
                _review_stage(connection, paper_id),
            ),
            "full_text_status": _full_text_status(lane, include_full_text, passages),
            "passages": passages,
        }


def _search_result(request: SearchResultRequest) -> JsonObject:
    lane = Lane(str(request.row["lane"]))
    return {
        "paper_id": str(request.row["paper_id"]),
        "title": str(request.row["title"]),
        "lane": lane.value,
        "metadata_only": _metadata_only(lane),
        "quarantine_status": _quarantine_status(lane, str(request.row[4])),
        "snippets": _snippets(
            SnippetRequest(
                request.connection,
                str(request.row["paper_id"]),
                request.query,
                lane,
            ),
        ),
    }


def _paper_json(row: sqlite3.Row) -> JsonObject:
    return {
        "paper_id": str(row["paper_id"]),
        "title": str(row["title"]),
        "lane": str(row["lane"]),
        "normalized_identifiers": str(row["normalized_identifiers"]),
        "created_at": str(row["created_at"]),
    }


def _instances(connection: sqlite3.Connection, paper_id: str) -> list[JsonObject]:
    rows = connection.execute(
        "SELECT instance_id, file_path, instance_status, discovered_at FROM paper_instance WHERE paper_id = ? ORDER BY instance_id",
        (paper_id,),
    ).fetchall()
    return [
        {
            "instance_id": str(row[0]),
            "file_path": str(row[1]),
            "instance_status": str(row[2]),
            "discovered_at": str(row[3]),
        }
        for row in rows
    ]


def _review_json(connection: sqlite3.Connection, paper_id: str) -> JsonObject | None:
    rows = review_queue_rows_for_paper(connection, paper_id)
    if not rows:
        return None
    return queue_item_json(rows[0])


def _review_stage(connection: sqlite3.Connection, paper_id: str) -> str:
    rows = review_queue_rows_for_paper(connection, paper_id)
    if not rows:
        return ""
    return str(rows[0][4])


def _artifacts(connection: sqlite3.Connection, paper_id: str) -> list[JsonObject]:
    rows = connection.execute(
        "SELECT artifact_id, artifact_kind, lane, stage_status, artifact_digest, created_at, artifact_path, vector_artifact_path "
        "FROM artifact_status WHERE paper_id = ? ORDER BY artifact_id",
        (paper_id,),
    ).fetchall()
    return [
        {
            "artifact_id": str(row[0]),
            "artifact_kind": str(row[1]),
            "lane": str(row[2]),
            "stage_status": str(row[3]),
            "artifact_digest": str(row[4]),
            "created_at": str(row[5]),
            "artifact_path": row[6],
            "vector_artifact_path": row[7],
        }
        for row in rows
    ]


def _paper_passages(request: PassageRequest) -> list[JsonObject]:
    if not request.include_full_text or _metadata_only(request.lane):
        return []
    rows = request.connection.execute(
        "SELECT passage_id, source_page, start_offset, end_offset, text, support_tag "
        "FROM extracted_passage WHERE paper_id = ? ORDER BY source_page, start_offset",
        (request.paper_id,),
    ).fetchall()
    return [
        {
            "passage_id": str(row[0]),
            "source_page": int(row[1]),
            "start_offset": int(row[2]),
            "end_offset": int(row[3]),
            "text": str(row[4]),
            "support_tag": str(row[5]),
        }
        for row in rows
    ]


def _snippets(request: SnippetRequest) -> list[str]:
    if _metadata_only(request.lane):
        return []
    rows = request.connection.execute(
        "SELECT text FROM extracted_passage WHERE paper_id = ? AND lower(text) LIKE ? ORDER BY source_page LIMIT 3",
        (request.paper_id, like_pattern(request.query)),
    ).fetchall()
    return [_snippet(str(row[0]), request.query) for row in rows]


def _snippet(text: str, query: str) -> str:
    index = text.casefold().find(query.casefold())
    start = max(index - 48, 0) if index >= 0 else 0
    end = min(start + 160, len(text))
    return text[start:end]


def _metadata_only(lane: Lane) -> bool:
    match lane:
        case Lane.RED:
            return True
        case Lane.GREEN | Lane.AMBER:
            return False
        case unreachable:
            assert_never(unreachable)


def _quarantine_status(lane: Lane, stage_status: str) -> str:
    match lane:
        case Lane.RED:
            return "quarantined"
        case Lane.GREEN | Lane.AMBER:
            return stage_status or "not_quarantined"
        case unreachable:
            assert_never(unreachable)


def _full_text_status(
    lane: Lane,
    include_full_text: bool,
    passages: list[JsonObject],
) -> str:
    match lane:
        case Lane.RED:
            return "metadata_only" if include_full_text else "not_requested"
        case Lane.GREEN | Lane.AMBER:
            if not include_full_text:
                return "not_requested"
            return "returned" if passages else "unavailable"
        case unreachable:
            assert_never(unreachable)
