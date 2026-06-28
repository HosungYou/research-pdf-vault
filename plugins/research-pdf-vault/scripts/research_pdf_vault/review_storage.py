from __future__ import annotations

import sqlite3
from typing import Final, TypeAlias

from research_pdf_vault.db import SCHEMA_VERSION, initialize_database
from research_pdf_vault.review_models import (
    ClassificationInsert,
    MergeInsert,
    ReviewItem,
    ReviewItemLookupError,
    ReviewStateUpdate,
)
from research_pdf_vault.review_policy import (
    classification_stage_for_lane,
    decision_id,
    merge_id,
    priority_for_lane,
    queue_item_id,
    synced_stage_for_lane,
)
from research_pdf_vault.schema import Lane, ReviewPriority, StageStatus

ReviewRow: TypeAlias = tuple[str, str, str, str, str, str, str, str]
REVIEW_SQL: Final = "\n".join(
    (
        "CREATE TABLE IF NOT EXISTS review_merge (merge_id TEXT PRIMARY KEY CHECK (merge_id GLOB 'merge_*'), source_paper_id TEXT NOT NULL REFERENCES paper(paper_id), target_paper_id TEXT NOT NULL REFERENCES paper(paper_id), actor TEXT NOT NULL, timestamp TEXT NOT NULL, reason TEXT NOT NULL CHECK (length(reason) > 0));",
    ),
)


def initialize_review_database(connection: sqlite3.Connection) -> None:
    initialize_database(connection)
    connection.executescript(REVIEW_SQL)


def list_review_items(
    connection: sqlite3.Connection,
    timestamp: str,
    manual_review_lanes: tuple[str, ...] = (Lane.AMBER.value, Lane.RED.value),
) -> tuple[ReviewItem, ...]:
    sync_required_review_items(connection, timestamp, manual_review_lanes)
    rows = connection.execute(
        "SELECT q.queue_item_id, q.paper_id, p.title, q.lane, q.stage_status, q.priority, q.reason, q.created_at "
        "FROM review_queue_item q JOIN paper p ON p.paper_id = q.paper_id "
        "WHERE q.lane != ? AND q.stage_status IN (?, ?, ?) "
        "ORDER BY CASE q.priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, q.created_at, q.paper_id",
        (
            Lane.GREEN.value,
            StageStatus.QUARANTINED.value,
            StageStatus.PENDING.value,
            StageStatus.RUNNING.value,
        ),
    ).fetchall()
    return tuple(review_item_from_row(row) for row in rows)


def show_review_item(
    connection: sqlite3.Connection,
    identifier: str,
    timestamp: str,
    manual_review_lanes: tuple[str, ...] = (Lane.AMBER.value, Lane.RED.value),
) -> ReviewItem | None:
    sync_required_review_items(connection, timestamp, manual_review_lanes)
    return load_review_item(connection, identifier)


def sync_required_review_items(
    connection: sqlite3.Connection,
    timestamp: str,
    manual_review_lanes: tuple[str, ...] = (Lane.AMBER.value, Lane.RED.value),
) -> None:
    selected_lanes = _selected_manual_lanes(manual_review_lanes)
    if not selected_lanes:
        return
    placeholders = ",".join("?" for _ in selected_lanes)
    rows = connection.execute(
        "SELECT p.paper_id, p.lane, p.created_at, "
        "COALESCE((SELECT c.reason FROM classification_decision c WHERE c.paper_id = p.paper_id ORDER BY c.timestamp DESC, c.decision_id DESC LIMIT 1), 'lane requires review') "
        f"FROM paper p WHERE p.lane IN ({placeholders}) "
        "AND NOT EXISTS (SELECT 1 FROM review_queue_item q WHERE q.paper_id = p.paper_id) "
        "ORDER BY p.paper_id",
        selected_lanes,
    ).fetchall()
    for paper_id, lane_value, created_at, reason in rows:
        lane = Lane(str(lane_value))
        connection.execute(
            "INSERT INTO review_queue_item (schema_version, queue_item_id, paper_id, lane, stage_status, priority, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                SCHEMA_VERSION,
                queue_item_id(str(paper_id)),
                str(paper_id),
                lane.value,
                synced_stage_for_lane(lane).value,
                priority_for_lane(lane).value,
                str(reason),
                str(created_at) if created_at is not None else timestamp,
            ),
        )


def _selected_manual_lanes(manual_review_lanes: tuple[str, ...]) -> tuple[str, ...]:
    allowed = frozenset((Lane.AMBER.value, Lane.RED.value))
    return tuple(lane for lane in manual_review_lanes if lane in allowed)


def review_item_from_row(row: ReviewRow) -> ReviewItem:
    return ReviewItem(
        queue_item_id=str(row[0]),
        paper_id=str(row[1]),
        title=str(row[2]),
        lane=Lane(str(row[3])),
        stage_status=StageStatus(str(row[4])),
        priority=ReviewPriority(str(row[5])),
        reason=str(row[6]),
        created_at=str(row[7]),
    )


def load_review_item(
    connection: sqlite3.Connection,
    identifier: str,
) -> ReviewItem | None:
    row = connection.execute(
        "SELECT q.queue_item_id, q.paper_id, p.title, q.lane, q.stage_status, q.priority, q.reason, q.created_at "
        "FROM review_queue_item q JOIN paper p ON p.paper_id = q.paper_id "
        "WHERE q.queue_item_id = ? OR q.paper_id = ? ORDER BY q.created_at LIMIT 1",
        (identifier, identifier),
    ).fetchone()
    if row is None:
        return None
    return review_item_from_row(row)


def require_review_item(connection: sqlite3.Connection, identifier: str) -> ReviewItem:
    item = load_review_item(connection, identifier)
    if item is None:
        raise ReviewItemLookupError(identifier=identifier)
    return item


def set_paper_lane(connection: sqlite3.Connection, paper_id: str, lane: Lane) -> None:
    connection.execute(
        "UPDATE paper SET lane = ? WHERE paper_id = ?",
        (lane.value, paper_id),
    )


def update_review_state(
    connection: sqlite3.Connection,
    state: ReviewStateUpdate,
) -> None:
    connection.execute(
        "UPDATE review_queue_item SET lane = ?, stage_status = ?, reason = ? WHERE queue_item_id = ?",
        (
            state.lane.value,
            state.stage_status.value,
            state.reason,
            state.queue_item_id,
        ),
    )


def insert_classification_decision(
    connection: sqlite3.Connection,
    entry: ClassificationInsert,
) -> None:
    connection.execute(
        "INSERT INTO classification_decision (schema_version, decision_id, paper_id, lane, stage_status, actor, timestamp, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            SCHEMA_VERSION,
            decision_id(entry),
            entry.paper_id,
            entry.lane.value,
            classification_stage_for_lane(entry.lane).value,
            entry.request.actor,
            entry.request.timestamp,
            entry.request.reason,
        ),
    )


def insert_review_merge(connection: sqlite3.Connection, entry: MergeInsert) -> None:
    connection.execute(
        "INSERT INTO review_merge (merge_id, source_paper_id, target_paper_id, actor, timestamp, reason) VALUES (?, ?, ?, ?, ?, ?)",
        (
            merge_id(entry),
            entry.source_paper_id,
            entry.target_paper_id,
            entry.request.actor,
            entry.request.timestamp,
            entry.request.reason,
        ),
    )


def paper_id_for_identifier(
    connection: sqlite3.Connection,
    identifier: str,
) -> str | None:
    item = load_review_item(connection, identifier)
    if item is not None:
        return item.paper_id
    row = connection.execute(
        "SELECT paper_id FROM paper WHERE paper_id = ?",
        (identifier,),
    ).fetchone()
    if row is None:
        return None
    return str(row[0])
