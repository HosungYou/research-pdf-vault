from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict, assert_never

from research_pdf_vault.claim_cards import ClaimCardCandidate
from research_pdf_vault.retrieval import TaskSupportTag
from research_pdf_vault.schema import CitationSlotId, ClaimId, PaperId


class CitationSlotOutput(TypedDict):
    citation_slot_id: str
    claim_id: str
    source: str
    page: int | None
    location: str
    passage: str
    proposed_claim: str
    support_tag: str
    confidence: float
    gap_reason: str


@dataclass(frozen=True, slots=True)
class CitationSlotCandidate:
    citation_slot_id: CitationSlotId
    claim_id: ClaimId
    paper_id: PaperId
    source: str
    page: int | None
    location: str
    passage: str
    proposed_claim: str
    support_tag: TaskSupportTag
    confidence: float
    gap_reason: str


def build_citation_slots(
    cards: tuple[ClaimCardCandidate, ...],
) -> tuple[CitationSlotCandidate, ...]:
    slots: list[CitationSlotCandidate] = []
    for card in cards:
        slot = _slot_for_card(card)
        if slot is not None:
            slots.append(slot)
    return tuple(slots)


def citation_slots_to_output(
    slots: tuple[CitationSlotCandidate, ...],
) -> list[CitationSlotOutput]:
    return [_slot_to_output(slot) for slot in slots]


def _slot_for_card(card: ClaimCardCandidate) -> CitationSlotCandidate | None:
    match card.support_tag:
        case TaskSupportTag.DIRECT_SUPPORT:
            return CitationSlotCandidate(
                citation_slot_id=_slot_id_for_claim(card.claim_id),
                claim_id=card.claim_id,
                paper_id=card.paper_id,
                source=card.source,
                page=card.page,
                location=card.location,
                passage=card.passage,
                proposed_claim=card.proposed_claim,
                support_tag=card.support_tag,
                confidence=card.confidence,
                gap_reason=card.gap_reason,
            )
        case TaskSupportTag.ANALOGY_ONLY | TaskSupportTag.GAP:
            return None
        case unreachable:
            assert_never(unreachable)


def _slot_to_output(slot: CitationSlotCandidate) -> CitationSlotOutput:
    return {
        "citation_slot_id": slot.citation_slot_id,
        "claim_id": slot.claim_id,
        "source": slot.source,
        "page": slot.page,
        "location": slot.location,
        "passage": slot.passage,
        "proposed_claim": slot.proposed_claim,
        "support_tag": slot.support_tag.value,
        "confidence": slot.confidence,
        "gap_reason": slot.gap_reason,
    }


def _slot_id_for_claim(claim_id: ClaimId) -> CitationSlotId:
    return CitationSlotId(f"slot_{str(claim_id).removeprefix('claim_')}")
