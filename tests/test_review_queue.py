from __future__ import annotations

import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
RPV: Final = SCRIPTS_DIR / "rpv.py"
SAMPLE_CONFIG: Final = ROOT / "fixtures" / "config" / "sample-config.toml"
sys.path.insert(0, str(SCRIPTS_DIR))


@dataclass(frozen=True, slots=True)
class SeedPaper:
    paper_id: str
    title: str
    lane: str
    stage_status: str
    reason: str


def test_review_list_when_green_amber_red_exist_then_green_is_omitted() -> None:
    from research_pdf_vault.review_queue import (
        initialize_review_database,
        list_review_items,
    )
    from research_pdf_vault.schema import Lane, StageStatus

    # Given
    seeds = (
        SeedPaper(
            paper_id="paper_green_001",
            title="Published public paper",
            lane="green",
            stage_status="complete",
            reason="public research article",
        ),
        SeedPaper(
            paper_id="paper_amber_001",
            title="Ambiguous conference deck",
            lane="amber",
            stage_status="pending",
            reason="ambiguous presentation deck",
        ),
        SeedPaper(
            paper_id="paper_red_001",
            title="Sensitive IRB notes",
            lane="red",
            stage_status="quarantined",
            reason="sensitive participant excerpt",
        ),
    )

    # When
    with sqlite3.connect(":memory:") as connection:
        initialize_review_database(connection)
        for seed in seeds:
            _seed_paper(connection, seed)
        items = list_review_items(connection, "2026-01-01T00:10:00Z")

    # Then
    items_by_paper_id = {item.paper_id: item for item in items}
    assert tuple(items_by_paper_id) == ("paper_red_001", "paper_amber_001")
    assert items_by_paper_id["paper_amber_001"].lane == Lane.AMBER
    assert items_by_paper_id["paper_red_001"].lane == Lane.RED
    assert items_by_paper_id["paper_amber_001"].stage_status == StageStatus.PENDING
    assert items_by_paper_id["paper_red_001"].stage_status == StageStatus.QUARANTINED
    assert items_by_paper_id["paper_amber_001"].reason == "ambiguous presentation deck"
    assert items_by_paper_id["paper_red_001"].reason == "sensitive participant excerpt"


def test_review_reclassify_when_amber_is_approved_then_ready_state_is_audited() -> None:
    from research_pdf_vault.review_queue import (
        ReviewApprovalRequest,
        ReviewMutationApplied,
        ReviewMutationRequest,
        initialize_review_database,
        list_review_items,
        review_approve,
        review_reclassify,
    )
    from research_pdf_vault.schema import Lane, StageStatus

    # Given
    seed = SeedPaper(
        paper_id="paper_amber_002",
        title="Ambiguous policy deck",
        lane="amber",
        stage_status="pending",
        reason="ambiguous source needs human review",
    )

    # When
    with sqlite3.connect(":memory:") as connection:
        initialize_review_database(connection)
        _seed_paper(connection, seed)
        [queued] = list_review_items(connection, "2026-01-01T00:10:00Z")
        reclassified = review_reclassify(
            connection,
            ReviewMutationRequest(
                identifier=queued.queue_item_id,
                actor="reviewer@example.com",
                reason="manual metadata confirms public report",
                timestamp="2026-01-01T00:11:00Z",
            ),
            Lane.GREEN,
        )
        approved = review_approve(
            connection,
            ReviewApprovalRequest(
                mutation=ReviewMutationRequest(
                    identifier=queued.queue_item_id,
                    actor="reviewer@example.com",
                    reason="approved after reclassification",
                    timestamp="2026-01-01T00:12:00Z",
                ),
                allow_sensitive=False,
            ),
        )
        audit_rows = connection.execute(
            "SELECT action, reason FROM audit_log ORDER BY timestamp",
        ).fetchall()
        paper_lane = connection.execute(
            "SELECT lane FROM paper WHERE paper_id = ?",
            (seed.paper_id,),
        ).fetchone()[0]

    # Then
    assert isinstance(reclassified, ReviewMutationApplied)
    assert isinstance(approved, ReviewMutationApplied)
    assert approved.item.lane == Lane.GREEN
    assert approved.item.stage_status == StageStatus.COMPLETE
    assert paper_lane == "green"
    assert audit_rows == [
        (
            "classify",
            "review reclassify to green by reviewer@example.com: manual metadata confirms public report",
        ),
        (
            "release",
            "review approve by reviewer@example.com: approved after reclassification",
        ),
    ]


def test_review_list_cli_when_manifest_is_empty_then_succeeds() -> None:
    # Given
    command = [
        sys.executable,
        str(RPV),
        "review",
        "list",
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
    assert completed.returncode == 0
    assert "review queue" in completed.stdout


def _seed_paper(connection: sqlite3.Connection, seed: SeedPaper) -> None:
    connection.execute(
        "INSERT INTO paper (schema_version, paper_id, title, normalized_identifiers, lane, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            "1.0.0",
            seed.paper_id,
            seed.title,
            '{"source":"test"}',
            seed.lane,
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
