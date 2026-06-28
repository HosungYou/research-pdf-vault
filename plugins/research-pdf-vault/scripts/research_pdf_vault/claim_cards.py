from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict, assert_never

from research_pdf_vault.retrieval import RetrievedPassage, TaskSupportTag
from research_pdf_vault.schema import ClaimId, PaperId, PassageId


class ClaimCardOutput(TypedDict):
    claim_id: str
    paper_id: str
    passage_id: str
    source: str
    page: int | None
    location: str
    passage: str
    proposed_claim: str
    support_tag: str
    confidence: float
    gap_reason: str
    eligible_for_core_claim: bool


@dataclass(frozen=True, slots=True)
class ClaimCardCandidate:
    claim_id: ClaimId
    paper_id: PaperId
    passage_id: PassageId
    source: str
    page: int | None
    location: str
    passage: str
    proposed_claim: str
    support_tag: TaskSupportTag
    confidence: float
    gap_reason: str
    eligible_for_core_claim: bool


def build_claim_cards(
    passages: tuple[RetrievedPassage, ...],
) -> tuple[ClaimCardCandidate, ...]:
    return tuple(_claim_card_for_passage(passage) for passage in passages)


def claim_cards_to_output(
    cards: tuple[ClaimCardCandidate, ...],
) -> list[ClaimCardOutput]:
    return [_claim_card_to_output(card) for card in cards]


def _claim_card_for_passage(passage: RetrievedPassage) -> ClaimCardCandidate:
    return ClaimCardCandidate(
        claim_id=_claim_id_for_passage(passage.passage_id),
        paper_id=passage.paper_id,
        passage_id=passage.passage_id,
        source=passage.source,
        page=passage.page,
        location=passage.location,
        passage=passage.passage,
        proposed_claim=passage.proposed_claim,
        support_tag=passage.support_tag,
        confidence=passage.confidence,
        gap_reason=passage.gap_reason,
        eligible_for_core_claim=_eligible_for_core_claim(passage.support_tag),
    )


def _claim_card_to_output(card: ClaimCardCandidate) -> ClaimCardOutput:
    return {
        "claim_id": card.claim_id,
        "paper_id": card.paper_id,
        "passage_id": card.passage_id,
        "source": card.source,
        "page": card.page,
        "location": card.location,
        "passage": card.passage,
        "proposed_claim": card.proposed_claim,
        "support_tag": card.support_tag.value,
        "confidence": card.confidence,
        "gap_reason": card.gap_reason,
        "eligible_for_core_claim": card.eligible_for_core_claim,
    }


def _claim_id_for_passage(passage_id: PassageId) -> ClaimId:
    return ClaimId(f"claim_{str(passage_id).removeprefix('passage_')}")


def _eligible_for_core_claim(support_tag: TaskSupportTag) -> bool:
    match support_tag:
        case TaskSupportTag.DIRECT_SUPPORT:
            return True
        case TaskSupportTag.ANALOGY_ONLY | TaskSupportTag.GAP:
            return False
        case unreachable:
            assert_never(unreachable)
