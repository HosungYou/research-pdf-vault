from __future__ import annotations

import sqlite3
from typing import assert_never

from research_pdf_vault.audit import AuditEvent, write_audit_event
from research_pdf_vault.review_models import (
    ClassificationInsert,
    MergeInsert,
    ReviewApprovalRequest,
    ReviewAudit,
    ReviewMergeRequest,
    ReviewMutationApplied,
    ReviewMutationMissing,
    ReviewMutationRequest,
    ReviewMutationRefused,
    ReviewMutationResult,
    ReviewStateUpdate,
)
from research_pdf_vault.review_policy import stage_after_reclassify
from research_pdf_vault.review_storage import (
    insert_classification_decision,
    insert_review_merge,
    load_review_item,
    paper_id_for_identifier,
    require_review_item,
    set_paper_lane,
    sync_required_review_items,
    update_review_state,
)
from research_pdf_vault.schema import AuditAction, Lane, StageStatus


def review_approve(
    connection: sqlite3.Connection,
    request: ReviewApprovalRequest,
) -> ReviewMutationResult:
    sync_required_review_items(connection, request.mutation.timestamp)
    item = load_review_item(connection, request.mutation.identifier)
    if item is None:
        return ReviewMutationMissing(identifier=request.mutation.identifier)
    match item.lane:
        case Lane.RED:
            if not request.allow_sensitive:
                reason = "red sensitive item requires --allow-sensitive"
                _write_review_audit(
                    connection,
                    ReviewAudit(
                        paper_id=item.paper_id,
                        request=request.mutation,
                        action=AuditAction.QUARANTINE,
                        action_reason=f"review approve refused by {request.mutation.actor}: {reason}",
                    ),
                )
                return ReviewMutationRefused(paper_id=item.paper_id, reason=reason)
        case Lane.GREEN | Lane.AMBER:
            pass
        case unreachable:
            assert_never(unreachable)
    set_paper_lane(connection, item.paper_id, Lane.GREEN)
    update_review_state(
        connection,
        ReviewStateUpdate(
            queue_item_id=item.queue_item_id,
            lane=Lane.GREEN,
            stage_status=StageStatus.COMPLETE,
            reason=request.mutation.reason,
        ),
    )
    _write_review_audit(
        connection,
        ReviewAudit(
            paper_id=item.paper_id,
            request=request.mutation,
            action=AuditAction.RELEASE,
            action_reason=(
                f"review approve by {request.mutation.actor}: "
                f"{request.mutation.reason}"
            ),
        ),
    )
    return ReviewMutationApplied(
        item=require_review_item(connection, item.queue_item_id),
    )


def review_reject(
    connection: sqlite3.Connection,
    request: ReviewMutationRequest,
) -> ReviewMutationResult:
    sync_required_review_items(connection, request.timestamp)
    item = load_review_item(connection, request.identifier)
    if item is None:
        return ReviewMutationMissing(identifier=request.identifier)
    update_review_state(
        connection,
        ReviewStateUpdate(
            queue_item_id=item.queue_item_id,
            lane=item.lane,
            stage_status=StageStatus.FAILED,
            reason=request.reason,
        ),
    )
    _write_review_audit(
        connection,
        ReviewAudit(
            paper_id=item.paper_id,
            request=request,
            action=AuditAction.UPDATE,
            action_reason=f"review reject by {request.actor}: {request.reason}",
        ),
    )
    return ReviewMutationApplied(item=require_review_item(connection, item.queue_item_id))


def review_reclassify(
    connection: sqlite3.Connection,
    request: ReviewMutationRequest,
    lane: Lane,
) -> ReviewMutationResult:
    sync_required_review_items(connection, request.timestamp)
    item = load_review_item(connection, request.identifier)
    if item is None:
        return ReviewMutationMissing(identifier=request.identifier)
    set_paper_lane(connection, item.paper_id, lane)
    insert_classification_decision(
        connection,
        ClassificationInsert(paper_id=item.paper_id, request=request, lane=lane),
    )
    update_review_state(
        connection,
        ReviewStateUpdate(
            queue_item_id=item.queue_item_id,
            lane=lane,
            stage_status=stage_after_reclassify(lane),
            reason=request.reason,
        ),
    )
    _write_review_audit(
        connection,
        ReviewAudit(
            paper_id=item.paper_id,
            request=request,
            action=AuditAction.CLASSIFY,
            action_reason=(
                f"review reclassify to {lane.value} by {request.actor}: "
                f"{request.reason}"
            ),
        ),
    )
    return ReviewMutationApplied(item=require_review_item(connection, item.queue_item_id))


def review_merge(
    connection: sqlite3.Connection,
    request: ReviewMergeRequest,
) -> ReviewMutationResult:
    sync_required_review_items(connection, request.source.timestamp)
    source = load_review_item(connection, request.source.identifier)
    if source is None:
        return ReviewMutationMissing(identifier=request.source.identifier)
    target_paper_id = paper_id_for_identifier(connection, request.target_identifier)
    if target_paper_id is None:
        return ReviewMutationMissing(identifier=request.target_identifier)
    insert_review_merge(
        connection,
        MergeInsert(
            source_paper_id=source.paper_id,
            target_paper_id=target_paper_id,
            request=request.source,
        ),
    )
    update_review_state(
        connection,
        ReviewStateUpdate(
            queue_item_id=source.queue_item_id,
            lane=source.lane,
            stage_status=StageStatus.COMPLETE,
            reason=request.source.reason,
        ),
    )
    _write_review_audit(
        connection,
        ReviewAudit(
            paper_id=source.paper_id,
            request=request.source,
            action=AuditAction.UPDATE,
            action_reason=(
                f"review merge by {request.source.actor}: "
                f"{source.paper_id} -> {target_paper_id}; {request.source.reason}"
            ),
        ),
    )
    return ReviewMutationApplied(
        item=require_review_item(connection, source.queue_item_id),
    )


def _write_review_audit(connection: sqlite3.Connection, audit: ReviewAudit) -> None:
    write_audit_event(
        connection,
        AuditEvent(
            paper_id=audit.paper_id,
            actor=audit.request.actor,
            timestamp=audit.request.timestamp,
            action=audit.action,
            reason=audit.action_reason,
        ),
    )
