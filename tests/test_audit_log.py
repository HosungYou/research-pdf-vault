from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@dataclass(frozen=True, slots=True)
class SeedPaper:
    paper_id: str
    lane: str
    stage_status: str
    reason: str
    file_path: str


def test_red_sensitive_approve_without_escape_hatch_is_refused_and_audited() -> None:
    from research_pdf_vault.review_queue import (
        ReviewApprovalRequest,
        ReviewMutationRefused,
        ReviewMutationRequest,
        initialize_review_database,
        list_review_items,
        review_approve,
    )
    from research_pdf_vault.schema import Lane, StageStatus

    # Given
    seed = SeedPaper(
        paper_id="paper_red_sensitive_001",
        lane="red",
        stage_status="quarantined",
        reason="sensitive_excerpt includes student participant consent",
        file_path="library/red-sensitive.pdf",
    )

    # When
    with sqlite3.connect(":memory:") as connection:
        initialize_review_database(connection)
        _seed_paper(connection, seed)
        [queued] = list_review_items(connection, "2026-01-01T00:10:00Z")
        result = review_approve(
            connection,
            ReviewApprovalRequest(
                mutation=ReviewMutationRequest(
                    identifier=queued.queue_item_id,
                    actor="agent-reviewer",
                    reason="attempted release for vectorization",
                    timestamp="2026-01-01T00:11:00Z",
                ),
                allow_sensitive=False,
            ),
        )
        item = list_review_items(connection, "2026-01-01T00:12:00Z")[0]
        audit_row = connection.execute(
            "SELECT action, reason FROM audit_log ORDER BY timestamp DESC LIMIT 1",
        ).fetchone()

    # Then
    assert isinstance(result, ReviewMutationRefused)
    assert result.paper_id == seed.paper_id
    assert item.lane == Lane.RED
    assert item.stage_status == StageStatus.QUARANTINED
    assert audit_row == (
        "quarantine",
        "review approve refused by agent-reviewer: red sensitive item requires --allow-sensitive",
    )


def test_reject_override_writes_audit_entry() -> None:
    from research_pdf_vault.review_queue import (
        ReviewMutationApplied,
        ReviewMutationRequest,
        initialize_review_database,
        list_review_items,
        review_reject,
    )
    from research_pdf_vault.schema import StageStatus

    # Given
    seed = SeedPaper(
        paper_id="paper_amber_reject_001",
        lane="amber",
        stage_status="pending",
        reason="duplicate conflict needs review",
        file_path="fixtures/review/reject.pdf",
    )

    # When
    with sqlite3.connect(":memory:") as connection:
        initialize_review_database(connection)
        _seed_paper(connection, seed)
        [queued] = list_review_items(connection, "2026-01-01T00:10:00Z")
        result = review_reject(
            connection,
            ReviewMutationRequest(
                identifier=queued.queue_item_id,
                actor="human-reviewer",
                reason="source is not suitable for this vault",
                timestamp="2026-01-01T00:14:00Z",
            ),
        )
        audit_row = connection.execute(
            "SELECT action, reason FROM audit_log ORDER BY timestamp DESC LIMIT 1",
        ).fetchone()

    # Then
    assert isinstance(result, ReviewMutationApplied)
    assert result.item.stage_status == StageStatus.FAILED
    assert audit_row == (
        "update",
        "review reject by human-reviewer: source is not suitable for this vault",
    )


def test_merge_when_source_pdf_exists_then_audit_is_written_without_file_mutation(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.review_queue import (
        ReviewMergeRequest,
        ReviewMutationApplied,
        ReviewMutationRequest,
        initialize_review_database,
        review_merge,
    )

    # Given
    source_pdf = tmp_path / "source.pdf"
    target_pdf = tmp_path / "target.pdf"
    source_bytes = b"%PDF-1.4\nsource synthetic content\n%%EOF\n"
    target_bytes = b"%PDF-1.4\ntarget synthetic content\n%%EOF\n"
    source_pdf.write_bytes(source_bytes)
    target_pdf.write_bytes(target_bytes)

    # When
    with sqlite3.connect(":memory:") as connection:
        initialize_review_database(connection)
        _seed_paper(
            connection,
            SeedPaper(
                paper_id="paper_merge_source_001",
                lane="amber",
                stage_status="pending",
                reason="duplicate_conflict",
                file_path="fixtures/review/source.pdf",
            ),
        )
        _seed_paper(
            connection,
            SeedPaper(
                paper_id="paper_merge_target_001",
                lane="green",
                stage_status="complete",
                reason="canonical public record",
                file_path="fixtures/review/target.pdf",
            ),
        )
        result = review_merge(
            connection,
            ReviewMergeRequest(
                source=ReviewMutationRequest(
                    identifier="paper_merge_source_001",
                    actor="reviewer@example.com",
                    reason="duplicate points to canonical record",
                    timestamp="2026-01-01T00:13:00Z",
                ),
                target_identifier="paper_merge_target_001",
            ),
        )
        audit_row = connection.execute(
            "SELECT action, reason FROM audit_log ORDER BY timestamp DESC LIMIT 1",
        ).fetchone()

    # Then
    assert isinstance(result, ReviewMutationApplied)
    assert source_pdf.read_bytes() == source_bytes
    assert target_pdf.read_bytes() == target_bytes
    assert audit_row == (
        "update",
        "review merge by reviewer@example.com: paper_merge_source_001 -> paper_merge_target_001; duplicate points to canonical record",
    )


def _seed_paper(connection: sqlite3.Connection, seed: SeedPaper) -> None:
    connection.execute(
        "INSERT INTO paper (schema_version, paper_id, title, normalized_identifiers, lane, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            "1.0.0",
            seed.paper_id,
            "Synthetic review paper",
            '{"source":"test"}',
            seed.lane,
            "2026-01-01T00:00:00Z",
        ),
    )
    connection.execute(
        "INSERT INTO paper_instance (schema_version, instance_id, paper_id, file_path, sha256, instance_status, discovered_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "1.0.0",
            f"instance_{seed.paper_id.removeprefix('paper_')}",
            seed.paper_id,
            seed.file_path,
            None,
            "available",
            "2026-01-01T00:00:00Z",
        ),
    )
    connection.execute(
        "INSERT INTO classification_decision (schema_version, decision_id, paper_id, lane, stage_status, actor, timestamp, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "1.0.0",
            f"decision_{seed.paper_id.removeprefix('paper_')}",
            seed.paper_id,
            seed.lane,
            seed.stage_status,
            "classifier",
            "2026-01-01T00:01:00Z",
            seed.reason,
        ),
    )
