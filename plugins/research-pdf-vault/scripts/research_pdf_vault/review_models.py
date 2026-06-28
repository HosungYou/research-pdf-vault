from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from research_pdf_vault.schema import AuditAction, Lane, ReviewPriority, StageStatus


@dataclass(frozen=True, slots=True)
class ReviewItem:
    queue_item_id: str
    paper_id: str
    title: str
    lane: Lane
    stage_status: StageStatus
    priority: ReviewPriority
    reason: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ReviewMutationRequest:
    identifier: str
    actor: str
    reason: str
    timestamp: str


@dataclass(frozen=True, slots=True)
class ReviewApprovalRequest:
    mutation: ReviewMutationRequest
    allow_sensitive: bool


@dataclass(frozen=True, slots=True)
class ReviewMergeRequest:
    source: ReviewMutationRequest
    target_identifier: str


@dataclass(frozen=True, slots=True)
class ReviewMutationApplied:
    item: ReviewItem


@dataclass(frozen=True, slots=True)
class ReviewMutationRefused:
    paper_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class ReviewMutationMissing:
    identifier: str


ReviewMutationResult: TypeAlias = (
    ReviewMutationApplied | ReviewMutationRefused | ReviewMutationMissing
)


@dataclass(frozen=True, slots=True)
class ReviewStateUpdate:
    queue_item_id: str
    lane: Lane
    stage_status: StageStatus
    reason: str


@dataclass(frozen=True, slots=True)
class ReviewAudit:
    paper_id: str
    request: ReviewMutationRequest
    action: AuditAction
    action_reason: str


@dataclass(frozen=True, slots=True)
class ClassificationInsert:
    paper_id: str
    request: ReviewMutationRequest
    lane: Lane


@dataclass(frozen=True, slots=True)
class MergeInsert:
    source_paper_id: str
    target_paper_id: str
    request: ReviewMutationRequest


@dataclass(frozen=True, slots=True)
class ReviewItemLookupError(Exception):
    identifier: str

    def __str__(self) -> str:
        return f"review item not found after mutation: {self.identifier}"
