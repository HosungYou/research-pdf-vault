from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import StrEnum, unique
from typing import assert_never

from research_pdf_vault.audit import AuditEvent, write_audit_event
from research_pdf_vault.config import VaultRuntimeConfig
from research_pdf_vault.mcp_types import JsonObject, McpToolError, bool_arg, string_arg
from research_pdf_vault.review_models import ReviewItem, ReviewStateUpdate
from research_pdf_vault.review_storage import (
    initialize_review_database,
    load_review_item,
    sync_required_review_items,
    update_review_state,
)
from research_pdf_vault.schema import AuditAction, Lane, StageStatus


@unique
class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    DEFER = "defer"
    QUARANTINE = "quarantine"


@dataclass(frozen=True, slots=True)
class ReviewDecisionInput:
    identifier: str
    decision: ReviewDecision
    actor: str
    reason: str
    timestamp: str
    allow_sensitive: bool


@dataclass(frozen=True, slots=True)
class ReviewApplyState:
    queue_item_id: str
    lane: Lane


@dataclass(frozen=True, slots=True)
class AuditWrite:
    paper_id: str
    action: AuditAction


def apply_review_decision(
    config: VaultRuntimeConfig,
    arguments: JsonObject,
) -> JsonObject:
    request = _decision_input(arguments)
    config.manifest_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.manifest_db) as connection:
        connection.row_factory = sqlite3.Row
        initialize_review_database(connection)
        sync_required_review_items(
            connection,
            request.timestamp,
            config.approval.manual_review_lanes,
        )
        item = load_review_item(connection, request.identifier)
        if item is None:
            return {"status": "missing", "identifier": request.identifier}
        match request.decision:
            case ReviewDecision.APPROVE:
                return _apply_approve(connection, request, item)
            case ReviewDecision.REJECT:
                return _apply_state(
                    connection,
                    request,
                    ReviewApplyState(item.queue_item_id, item.lane),
                )
            case ReviewDecision.DEFER:
                return _apply_state(
                    connection,
                    request,
                    ReviewApplyState(item.queue_item_id, item.lane),
                )
            case ReviewDecision.QUARANTINE:
                return _apply_state(
                    connection,
                    request,
                    ReviewApplyState(item.queue_item_id, Lane.RED),
                )
            case unreachable:
                assert_never(unreachable)


def _decision_input(arguments: JsonObject) -> ReviewDecisionInput:
    raw_decision = string_arg(arguments, "decision")
    try:
        decision = ReviewDecision(raw_decision)
    except ValueError as error:
        raise McpToolError(f"unsupported review decision: {raw_decision}") from error
    return ReviewDecisionInput(
        identifier=string_arg(arguments, "identifier"),
        decision=decision,
        actor=string_arg(arguments, "actor"),
        reason=string_arg(arguments, "reason"),
        timestamp=string_arg(arguments, "timestamp"),
        allow_sensitive=bool_arg(arguments, "allow_sensitive", False),
    )


def _apply_approve(
    connection: sqlite3.Connection,
    request: ReviewDecisionInput,
    item: ReviewItem,
) -> JsonObject:
    match item.lane:
        case Lane.RED:
            if not request.allow_sensitive:
                _audit(
                    connection,
                    request,
                    AuditWrite(item.paper_id, AuditAction.QUARANTINE),
                )
                return {
                    "status": "refused",
                    "reason": "red sensitive item requires allow_sensitive",
                }
        case Lane.GREEN | Lane.AMBER:
            pass
        case unreachable:
            assert_never(unreachable)
    return _apply_state(
        connection,
        request,
        ReviewApplyState(item.queue_item_id, Lane.GREEN),
    )


def _apply_state(
    connection: sqlite3.Connection,
    request: ReviewDecisionInput,
    state: ReviewApplyState,
) -> JsonObject:
    update_review_state(
        connection,
        ReviewStateUpdate(
            queue_item_id=state.queue_item_id,
            lane=state.lane,
            stage_status=_stage_for_decision(request.decision),
            reason=request.reason,
        ),
    )
    item = load_review_item(connection, state.queue_item_id)
    if item is None:
        return {"status": "missing", "identifier": state.queue_item_id}
    _audit(connection, request, AuditWrite(item.paper_id, _audit_action(request.decision)))
    return {"status": "applied", "item": _queue_item_from_review(item)}


def _stage_for_decision(decision: ReviewDecision) -> StageStatus:
    match decision:
        case ReviewDecision.APPROVE:
            return StageStatus.COMPLETE
        case ReviewDecision.REJECT:
            return StageStatus.FAILED
        case ReviewDecision.DEFER:
            return StageStatus.PENDING
        case ReviewDecision.QUARANTINE:
            return StageStatus.QUARANTINED
        case unreachable:
            assert_never(unreachable)


def _audit_action(decision: ReviewDecision) -> AuditAction:
    match decision:
        case ReviewDecision.APPROVE:
            return AuditAction.RELEASE
        case ReviewDecision.REJECT | ReviewDecision.DEFER:
            return AuditAction.UPDATE
        case ReviewDecision.QUARANTINE:
            return AuditAction.QUARANTINE
        case unreachable:
            assert_never(unreachable)


def _audit(
    connection: sqlite3.Connection,
    request: ReviewDecisionInput,
    audit: AuditWrite,
) -> None:
    write_audit_event(
        connection,
        AuditEvent(
            paper_id=audit.paper_id,
            actor=request.actor,
            timestamp=request.timestamp,
            action=audit.action,
            reason=f"mcp {request.decision.value} by {request.actor}: {request.reason}",
        ),
    )


def _queue_item_from_review(item: ReviewItem) -> JsonObject:
    return {
        "queue_item_id": item.queue_item_id,
        "paper_id": item.paper_id,
        "title": item.title,
        "lane": item.lane.value,
        "stage_status": item.stage_status.value,
        "priority": item.priority.value,
        "reason": item.reason,
        "created_at": item.created_at,
    }
