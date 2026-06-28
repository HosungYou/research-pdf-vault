from __future__ import annotations

from dataclasses import dataclass
from typing import Final, assert_never

from research_pdf_vault.document_traits import DocumentTraits
from research_pdf_vault.schema import Lane

DEFAULT_OCR_CHAR_LIMIT: Final = 4000


@dataclass(frozen=True, slots=True)
class OcrPolicy:
    allow_green_ocr: bool
    allow_amber_constrained_ocr: bool
    max_chars: int = DEFAULT_OCR_CHAR_LIMIT


@dataclass(frozen=True, slots=True)
class OcrPolicyRequest:
    lane: Lane
    traits: DocumentTraits
    policy: OcrPolicy


@dataclass(frozen=True, slots=True)
class OcrPolicyDecision:
    allowed: bool
    constrained: bool
    reason_code: str
    max_chars: int


DEFAULT_OCR_POLICY: Final = OcrPolicy(
    allow_green_ocr=True,
    allow_amber_constrained_ocr=False,
)


def ocr_policy_decision(request: OcrPolicyRequest) -> OcrPolicyDecision:
    safety_reason = _safety_block_reason(request.traits)
    if safety_reason is not None:
        return OcrPolicyDecision(
            allowed=False,
            constrained=False,
            reason_code=safety_reason,
            max_chars=request.policy.max_chars,
        )
    match request.lane:
        case Lane.GREEN:
            return _green_decision(request.policy)
        case Lane.AMBER:
            return _amber_decision(request.policy)
        case Lane.RED:
            return OcrPolicyDecision(
                allowed=False,
                constrained=False,
                reason_code="red_lane_never_ocr",
                max_chars=request.policy.max_chars,
            )
        case unreachable:
            assert_never(unreachable)


def _safety_block_reason(traits: DocumentTraits) -> str | None:
    if traits.encrypted:
        return "encrypted_pdf_blocked"
    if traits.corrupt:
        return "corrupt_pdf_blocked"
    return None


def _green_decision(policy: OcrPolicy) -> OcrPolicyDecision:
    if policy.allow_green_ocr:
        return OcrPolicyDecision(
            allowed=True,
            constrained=False,
            reason_code="green_ocr_allowed",
            max_chars=policy.max_chars,
        )
    return OcrPolicyDecision(
        allowed=False,
        constrained=False,
        reason_code="green_ocr_disabled",
        max_chars=policy.max_chars,
    )


def _amber_decision(policy: OcrPolicy) -> OcrPolicyDecision:
    if policy.allow_amber_constrained_ocr:
        return OcrPolicyDecision(
            allowed=True,
            constrained=True,
            reason_code="amber_constrained_ocr_allowed",
            max_chars=policy.max_chars,
        )
    return OcrPolicyDecision(
        allowed=False,
        constrained=False,
        reason_code="amber_ocr_requires_constrained_policy",
        max_chars=policy.max_chars,
    )
