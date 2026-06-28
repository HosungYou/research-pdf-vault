from __future__ import annotations

import hashlib
from typing import Final, assert_never

from research_pdf_vault.review_models import ClassificationInsert, MergeInsert
from research_pdf_vault.schema import Lane, ReviewPriority, StageStatus

HASH_ID_LENGTH: Final = 24


def synced_stage_for_lane(lane: Lane) -> StageStatus:
    match lane:
        case Lane.AMBER:
            return StageStatus.PENDING
        case Lane.RED:
            return StageStatus.QUARANTINED
        case Lane.GREEN:
            return StageStatus.COMPLETE
        case unreachable:
            assert_never(unreachable)


def priority_for_lane(lane: Lane) -> ReviewPriority:
    match lane:
        case Lane.RED:
            return ReviewPriority.HIGH
        case Lane.AMBER:
            return ReviewPriority.NORMAL
        case Lane.GREEN:
            return ReviewPriority.LOW
        case unreachable:
            assert_never(unreachable)


def stage_after_reclassify(lane: Lane) -> StageStatus:
    match lane:
        case Lane.GREEN | Lane.AMBER:
            return StageStatus.PENDING
        case Lane.RED:
            return StageStatus.QUARANTINED
        case unreachable:
            assert_never(unreachable)


def classification_stage_for_lane(lane: Lane) -> StageStatus:
    match lane:
        case Lane.GREEN:
            return StageStatus.COMPLETE
        case Lane.AMBER:
            return StageStatus.PENDING
        case Lane.RED:
            return StageStatus.QUARANTINED
        case unreachable:
            assert_never(unreachable)


def queue_item_id(paper_id: str) -> str:
    return f"queue_{digest_text(paper_id)}"


def decision_id(entry: ClassificationInsert) -> str:
    key = (
        f"{entry.paper_id}:{entry.lane.value}:"
        f"{entry.request.timestamp}:{entry.request.reason}"
    )
    return f"decision_{digest_text(key)}"


def merge_id(entry: MergeInsert) -> str:
    key = (
        f"{entry.source_paper_id}:{entry.target_paper_id}:"
        f"{entry.request.timestamp}:{entry.request.reason}"
    )
    return f"merge_{digest_text(key)}"


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:HASH_ID_LENGTH]
