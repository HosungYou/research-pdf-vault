from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
FIXTURE_ROOT: Final = ROOT / "fixtures" / "citations"
RPV: Final = SCRIPTS_DIR / "rpv.py"
SAMPLE_CONFIG: Final = ROOT / "fixtures" / "config" / "sample-config.toml"
sys.path.insert(0, str(SCRIPTS_DIR))


def test_citation_slots_when_cards_have_analogy_and_gap_then_emit_only_direct_support() -> None:
    # Given
    from research_pdf_vault.citation_slots import build_citation_slots
    from research_pdf_vault.claim_cards import build_claim_cards
    from research_pdf_vault.retrieval import retrieve_fixture_passages

    cards = build_claim_cards(retrieve_fixture_passages(FIXTURE_ROOT, "sample-aidt"))

    # When
    slots = build_citation_slots(cards)

    # Then
    assert len(slots) == 1
    assert slots[0].support_tag.value == "direct_support"
    assert slots[0].source == "sample-aidt/direct-learning-gains.pdf"
    assert slots[0].page == 4
    assert slots[0].gap_reason == ""


def test_citation_slot_output_when_serialized_then_includes_required_citation_fields() -> None:
    # Given
    from research_pdf_vault.citation_slots import (
        build_citation_slots,
        citation_slots_to_output,
    )
    from research_pdf_vault.claim_cards import build_claim_cards
    from research_pdf_vault.retrieval import retrieve_fixture_passages

    cards = build_claim_cards(retrieve_fixture_passages(FIXTURE_ROOT, "sample-aidt"))

    # When
    output = citation_slots_to_output(build_citation_slots(cards))

    # Then
    assert output == [
        {
            "citation_slot_id": "slot_sample_aidt_direct_001",
            "claim_id": "claim_sample_aidt_direct_001",
            "source": "sample-aidt/direct-learning-gains.pdf",
            "page": 4,
            "location": "p. 4, results",
            "passage": "In a randomized classroom study, AI tutoring improved algebra post-test scores by 12 percentage points compared with conventional homework.",
            "proposed_claim": "AI tutoring improved algebra post-test scores by 12 percentage points in a randomized classroom study.",
            "support_tag": "direct_support",
            "confidence": 0.93,
            "gap_reason": "",
        },
    ]


def test_cli_citation_slots_build_when_sample_project_then_outputs_direct_slot_only() -> None:
    # Given
    command = [
        sys.executable,
        str(RPV),
        "citation-slots",
        "build",
        "--config",
        str(SAMPLE_CONFIG),
        "--project",
        "sample-aidt",
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
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["project"] == "sample-aidt"
    assert [slot["support_tag"] for slot in payload["citation_slots"]] == [
        "direct_support",
    ]
    assert payload["citation_slots"][0]["page"] == 4
    assert {card["support_tag"] for card in payload["claim_cards"]} == {
        "direct_support",
        "analogy_only",
        "gap",
    }
