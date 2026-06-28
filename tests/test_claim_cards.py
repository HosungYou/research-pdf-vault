from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
FIXTURE_ROOT: Final = ROOT / "fixtures" / "citations"
sys.path.insert(0, str(SCRIPTS_DIR))


def test_claim_cards_when_fixture_has_mixed_support_then_tags_core_eligibility() -> None:
    # Given
    from research_pdf_vault.claim_cards import TaskSupportTag, build_claim_cards
    from research_pdf_vault.retrieval import retrieve_fixture_passages

    passages = retrieve_fixture_passages(FIXTURE_ROOT, "sample-aidt")

    # When
    cards = build_claim_cards(passages)

    # Then
    assert [card.support_tag for card in cards] == [
        TaskSupportTag.DIRECT_SUPPORT,
        TaskSupportTag.ANALOGY_ONLY,
        TaskSupportTag.GAP,
    ]
    assert [card.eligible_for_core_claim for card in cards] == [True, False, False]
    assert cards[0].proposed_claim.startswith("AI tutoring improved")
    assert cards[1].gap_reason.startswith("Analogy does not directly")
    assert cards[2].gap_reason.startswith("Metadata-only record")


def test_claim_card_output_when_serialized_then_includes_required_citation_fields() -> None:
    # Given
    from research_pdf_vault.claim_cards import build_claim_cards, claim_cards_to_output
    from research_pdf_vault.retrieval import retrieve_fixture_passages

    cards = build_claim_cards(retrieve_fixture_passages(FIXTURE_ROOT, "sample-aidt"))

    # When
    output = claim_cards_to_output(cards)

    # Then
    for candidate in output:
        assert set(candidate) >= {
            "source",
            "page",
            "location",
            "passage",
            "proposed_claim",
            "support_tag",
            "confidence",
            "gap_reason",
        }
    assert output[0]["support_tag"] == "direct_support"
    assert output[0]["page"] == 4
    assert output[2]["support_tag"] == "gap"
