from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from typing import Final

from research_pdf_vault.db import SCHEMA_VERSION
from research_pdf_vault.schema import AuditAction

HASH_ID_LENGTH: Final = 24


@dataclass(frozen=True, slots=True)
class AuditEvent:
    paper_id: str
    actor: str
    timestamp: str
    action: AuditAction
    reason: str


def write_audit_event(connection: sqlite3.Connection, event: AuditEvent) -> None:
    connection.execute(
        "INSERT INTO audit_log (schema_version, audit_id, paper_id, actor, timestamp, action, reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            SCHEMA_VERSION,
            _audit_id(event),
            event.paper_id,
            event.actor,
            event.timestamp,
            event.action.value,
            event.reason,
        ),
    )


def _audit_id(event: AuditEvent) -> str:
    digest = hashlib.sha256(
        "\n".join(
            (
                event.paper_id,
                event.actor,
                event.timestamp,
                event.action.value,
                event.reason,
            ),
        ).encode("utf-8"),
    ).hexdigest()
    return f"audit_{digest[:HASH_ID_LENGTH]}"
