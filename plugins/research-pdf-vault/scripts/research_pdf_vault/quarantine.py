from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, assert_never

from research_pdf_vault.schema import Lane, StageStatus


@dataclass(frozen=True, slots=True)
class AllowedStages:
    can_extract_text: bool
    can_ocr: bool
    can_vectorize: bool


@dataclass(frozen=True, slots=True)
class QuarantinePolicy:
    quarantine_required: bool
    metadata_only: bool
    stage_status: StageStatus
    allowed_stages: AllowedStages


class ClassificationDecisionLike(Protocol):
    lane: Lane
    stage_status: StageStatus
    metadata_only: bool
    allowed_stages: AllowedStages


def allowed_stages_for_lane(lane: Lane) -> AllowedStages:
    match lane:
        case Lane.GREEN:
            return AllowedStages(
                can_extract_text=True,
                can_ocr=True,
                can_vectorize=True,
            )
        case Lane.AMBER:
            return AllowedStages(
                can_extract_text=True,
                can_ocr=True,
                can_vectorize=False,
            )
        case Lane.RED:
            return AllowedStages(
                can_extract_text=False,
                can_ocr=False,
                can_vectorize=False,
            )
        case unreachable:
            assert_never(unreachable)


def stage_status_for_lane(lane: Lane) -> StageStatus:
    match lane:
        case Lane.GREEN:
            return StageStatus.COMPLETE
        case Lane.AMBER:
            return StageStatus.PENDING
        case Lane.RED:
            return StageStatus.QUARANTINED
        case unreachable:
            assert_never(unreachable)


def quarantine_policy_for(decision: ClassificationDecisionLike) -> QuarantinePolicy:
    return QuarantinePolicy(
        quarantine_required=decision.lane == Lane.RED,
        metadata_only=decision.metadata_only,
        stage_status=decision.stage_status,
        allowed_stages=decision.allowed_stages,
    )
