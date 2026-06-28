from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from research_pdf_vault.mcp_types import JsonObject


@dataclass(frozen=True, slots=True)
class WorkerReportRecord:
    report_id: str
    worker_name: str
    paper_id: str
    stage_status: str
    started_at: str
    finished_at: str
    artifact_digest: str
    summary: str

    def to_json(self) -> JsonObject:
        return {
            "report_id": self.report_id,
            "worker_name": self.worker_name,
            "paper_id": self.paper_id,
            "stage_status": self.stage_status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "artifact_digest": self.artifact_digest,
            "summary": self.summary,
        }


def list_worker_reports(connection: sqlite3.Connection) -> list[JsonObject]:
    rows = connection.execute(
        "SELECT report_id, worker_name, paper_id, stage_status, started_at, finished_at, artifact_digest, summary "
        "FROM worker_report ORDER BY finished_at DESC, report_id",
    ).fetchall()
    return [_report_from_row(row).to_json() for row in rows]


def get_worker_report(
    connection: sqlite3.Connection,
    report_id: str,
) -> JsonObject | None:
    row = connection.execute(
        "SELECT report_id, worker_name, paper_id, stage_status, started_at, finished_at, artifact_digest, summary "
        "FROM worker_report WHERE report_id = ?",
        (report_id,),
    ).fetchone()
    if row is None:
        return None
    return _report_from_row(row).to_json()


def _report_from_row(row: sqlite3.Row) -> WorkerReportRecord:
    return WorkerReportRecord(
        report_id=str(row[0]),
        worker_name=str(row[1]),
        paper_id=str(row[2]),
        stage_status=str(row[3]),
        started_at=str(row[4]),
        finished_at=str(row[5]),
        artifact_digest=str(row[6]),
        summary=str(row[7]),
    )
