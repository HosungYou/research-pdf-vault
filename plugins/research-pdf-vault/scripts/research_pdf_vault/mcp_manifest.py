from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Final

from research_pdf_vault.config import VaultRuntimeConfig
from research_pdf_vault.mcp_db import count_table, open_read_connection, review_queue_items
from research_pdf_vault.mcp_types import IntArgSpec, JsonObject, bounded_int_arg

MAX_REVIEW_LIMIT: Final = 50
REVIEW_LIMIT_ARG: Final = IntArgSpec("limit", MAX_REVIEW_LIMIT, 1, MAX_REVIEW_LIMIT)


def get_manifest_summary(config: VaultRuntimeConfig) -> JsonObject:
    connection = open_read_connection(config)
    if connection is None:
        return _empty_summary(config)
    with closing(connection):
        return {
            "counts": {
                "papers": count_table(connection, "paper"),
                "instances": count_table(connection, "paper_instance"),
                "review_queue_items": count_table(connection, "review_queue_item"),
                "reports": count_table(connection, "worker_report"),
            },
            "lanes": _lane_counts(connection),
            "review_queue": _review_counts(connection),
            "privacy": _privacy_json(config),
            "long_running_jobs": "not_triggered",
        }


def list_review_queue(config: VaultRuntimeConfig, arguments: JsonObject) -> JsonObject:
    limit = bounded_int_arg(arguments, REVIEW_LIMIT_ARG)
    connection = open_read_connection(config)
    if connection is None:
        return {"items": []}
    with closing(connection):
        return {"items": review_queue_items(connection, limit)}


def _empty_summary(config: VaultRuntimeConfig) -> JsonObject:
    return {
        "counts": {"papers": 0, "instances": 0, "review_queue_items": 0, "reports": 0},
        "lanes": {"green": 0, "amber": 0, "red": 0},
        "review_queue": {},
        "privacy": _privacy_json(config),
        "long_running_jobs": "not_triggered",
    }


def _privacy_json(config: VaultRuntimeConfig) -> JsonObject:
    return {
        "red_lane_metadata_only": config.privacy.red_lane_metadata_only,
        "allow_external_pdf_upload": config.privacy.allow_external_pdf_upload,
    }


def _lane_counts(connection: sqlite3.Connection) -> JsonObject:
    counts: JsonObject = {"green": 0, "amber": 0, "red": 0}
    rows = connection.execute("SELECT lane, COUNT(*) FROM paper GROUP BY lane").fetchall()
    for lane, count in rows:
        counts[str(lane)] = int(count)
    return counts


def _review_counts(connection: sqlite3.Connection) -> JsonObject:
    counts: JsonObject = {}
    rows = connection.execute(
        "SELECT stage_status, COUNT(*) FROM review_queue_item GROUP BY stage_status",
    ).fetchall()
    for stage_status, count in rows:
        counts[str(stage_status)] = int(count)
    return counts
