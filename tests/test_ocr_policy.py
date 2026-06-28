from __future__ import annotations

import sys
from pathlib import Path
from typing import Final, assert_never

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def test_default_policy_allows_green_ocr_and_blocks_amber_and_red() -> None:
    from research_pdf_vault.document_traits import DocumentTraits
    from research_pdf_vault.ocr_policy import (
        DEFAULT_OCR_POLICY,
        OcrPolicyDecision,
        OcrPolicyRequest,
        ocr_policy_decision,
    )
    from research_pdf_vault.schema import Lane

    # Given
    traits = DocumentTraits()

    # When
    green = ocr_policy_decision(
        OcrPolicyRequest(lane=Lane.GREEN, traits=traits, policy=DEFAULT_OCR_POLICY),
    )
    amber = ocr_policy_decision(
        OcrPolicyRequest(lane=Lane.AMBER, traits=traits, policy=DEFAULT_OCR_POLICY),
    )
    red = ocr_policy_decision(
        OcrPolicyRequest(lane=Lane.RED, traits=traits, policy=DEFAULT_OCR_POLICY),
    )

    # Then
    decisions: tuple[OcrPolicyDecision, ...] = (green, amber, red)
    assert tuple(decision.allowed for decision in decisions) == (True, False, False)
    assert green.reason_code == "green_ocr_allowed"
    assert amber.reason_code == "amber_ocr_requires_constrained_policy"
    assert red.reason_code == "red_lane_never_ocr"


def test_constrained_policy_allows_amber_ocr_but_never_red() -> None:
    from research_pdf_vault.document_traits import DocumentTraits
    from research_pdf_vault.ocr_policy import OcrPolicy, OcrPolicyRequest, ocr_policy_decision
    from research_pdf_vault.schema import Lane

    # Given
    policy = OcrPolicy(allow_green_ocr=True, allow_amber_constrained_ocr=True)
    traits = DocumentTraits()

    # When
    amber = ocr_policy_decision(
        OcrPolicyRequest(lane=Lane.AMBER, traits=traits, policy=policy),
    )
    red = ocr_policy_decision(
        OcrPolicyRequest(lane=Lane.RED, traits=traits, policy=policy),
    )

    # Then
    assert amber.allowed is True
    assert amber.constrained is True
    assert amber.reason_code == "amber_constrained_ocr_allowed"
    assert red.allowed is False
    assert red.reason_code == "red_lane_never_ocr"


def test_safety_traits_block_ocr_before_lane_allowance() -> None:
    from research_pdf_vault.document_traits import DocumentTraits
    from research_pdf_vault.ocr_policy import (
        DEFAULT_OCR_POLICY,
        OcrPolicyRequest,
        ocr_policy_decision,
    )
    from research_pdf_vault.schema import Lane

    # Given / When
    encrypted = ocr_policy_decision(
        OcrPolicyRequest(
            lane=Lane.GREEN,
            traits=DocumentTraits(encrypted=True),
            policy=DEFAULT_OCR_POLICY,
        ),
    )
    corrupt = ocr_policy_decision(
        OcrPolicyRequest(
            lane=Lane.GREEN,
            traits=DocumentTraits(corrupt=True),
            policy=DEFAULT_OCR_POLICY,
        ),
    )

    # Then
    assert encrypted.allowed is False
    assert encrypted.reason_code == "encrypted_pdf_blocked"
    assert corrupt.allowed is False
    assert corrupt.reason_code == "corrupt_pdf_blocked"


def test_policy_decisions_only_use_green_amber_red_lanes() -> None:
    from research_pdf_vault.document_traits import DocumentTraits
    from research_pdf_vault.ocr_policy import (
        DEFAULT_OCR_POLICY,
        OcrPolicyRequest,
        ocr_policy_decision,
    )
    from research_pdf_vault.schema import Lane

    # Given / When / Then
    for lane in Lane:
        decision = ocr_policy_decision(
            OcrPolicyRequest(
                lane=lane,
                traits=DocumentTraits(),
                policy=DEFAULT_OCR_POLICY,
            ),
        )
        match lane:
            case Lane.GREEN:
                assert decision.allowed is True
            case Lane.AMBER | Lane.RED:
                assert decision.allowed is False
            case unreachable:
                assert_never(unreachable)
