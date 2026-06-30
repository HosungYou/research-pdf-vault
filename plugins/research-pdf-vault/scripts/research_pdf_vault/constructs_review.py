from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from research_pdf_vault.config import VaultRuntimeConfig
from research_pdf_vault.constructs import initialize_construct_tables
from research_pdf_vault.db import initialize_database


@dataclass(frozen=True, slots=True)
class ConstructReviewError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class ConstructReviewAction:
    candidate_id: str
    actor: str
    reason: str
    target_construct_id: str | None = None


@dataclass(frozen=True, slots=True)
class ConstructReviewResult:
    action: str
    candidate_id: str


def list_review_candidates(config: VaultRuntimeConfig) -> tuple[str, ...]:
    with sqlite3.connect(config.manifest_db) as connection:
        initialize_database(connection)
        initialize_construct_tables(connection)
        rows = connection.execute(
            "SELECT candidate_id, reported_term, candidate_normalization, measurement_proxy, theoretical_role, confidence "
            "FROM construct_candidate WHERE review_required = 1 AND candidate_status = 'pending' "
            "ORDER BY reported_term, candidate_id",
        )
        return tuple(
            " | ".join(
                (
                    str(candidate_id),
                    str(reported_term),
                    str(candidate_normalization),
                    str(measurement_proxy),
                    str(theoretical_role),
                    f"{float(confidence):.2f}",
                ),
            )
            for (
                candidate_id,
                reported_term,
                candidate_normalization,
                measurement_proxy,
                theoretical_role,
                confidence,
            ) in rows
        )


def approve_candidate(
    config: VaultRuntimeConfig,
    action: ConstructReviewAction,
) -> ConstructReviewResult:
    return _set_candidate_status(config, action, "approved", "approve")


def reject_candidate(
    config: VaultRuntimeConfig,
    action: ConstructReviewAction,
) -> ConstructReviewResult:
    return _set_candidate_status(config, action, "rejected", "reject")


def reassign_candidate(
    config: VaultRuntimeConfig,
    action: ConstructReviewAction,
) -> ConstructReviewResult:
    if action.target_construct_id is None:
        raise ConstructReviewError("target construct is required")
    with sqlite3.connect(config.manifest_db) as connection:
        initialize_database(connection)
        initialize_construct_tables(connection)
        _require_candidate(connection, action.candidate_id)
        _require_construct(connection, action.target_construct_id)
        connection.execute(
            "UPDATE construct_candidate SET construct_id = ?, candidate_status = 'approved', review_required = 0 WHERE candidate_id = ?",
            (action.target_construct_id, action.candidate_id),
        )
    return ConstructReviewResult(action="reassign", candidate_id=action.candidate_id)


def _set_candidate_status(
    config: VaultRuntimeConfig,
    action: ConstructReviewAction,
    status: str,
    action_name: str,
) -> ConstructReviewResult:
    with sqlite3.connect(config.manifest_db) as connection:
        initialize_database(connection)
        initialize_construct_tables(connection)
        _require_candidate(connection, action.candidate_id)
        connection.execute(
            "UPDATE construct_candidate SET candidate_status = ?, review_required = 0 WHERE candidate_id = ?",
            (status, action.candidate_id),
        )
    return ConstructReviewResult(action=action_name, candidate_id=action.candidate_id)


def _require_candidate(connection: sqlite3.Connection, candidate_id: str) -> None:
    row = connection.execute(
        "SELECT 1 FROM construct_candidate WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()
    if row is None:
        raise ConstructReviewError(f"unknown construct candidate: {candidate_id}")


def _require_construct(connection: sqlite3.Connection, construct_id: str) -> None:
    row = connection.execute(
        "SELECT 1 FROM construct_registry WHERE construct_id = ?",
        (construct_id,),
    ).fetchone()
    if row is None:
        raise ConstructReviewError(f"unknown construct: {construct_id}")
