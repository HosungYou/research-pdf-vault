from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, assert_never

from research_pdf_vault.document_traits import (
    DocumentClassificationInput,
    DocumentTypeHint,
    LocalLLMAdapter,
    LocalLLMStatus,
    local_llm_request_for,
)
from research_pdf_vault.quarantine import (
    AllowedStages,
    allowed_stages_for_lane,
    stage_status_for_lane,
)
from research_pdf_vault.schema import Lane, StageStatus

TOKEN_RE: Final = re.compile(r"[a-z0-9]+")
RESTRICTED_PATH_TOKENS: Final = frozenset(
    ("restricted", "private", "sensitive", "confidential", "irb", "student"),
)
AMBER_PATH_TOKENS: Final = frozenset(("draft", "slides", "deck", "presentation"))
OFFICIAL_TEXT_TOKENS: Final = frozenset(("official", "report", "published"))
RESEARCH_TEXT_TOKENS: Final = frozenset(("abstract", "methods", "results"))
SENSITIVE_TEXT_TOKENS: Final = frozenset(
    ("irb", "student", "participant", "consent", "interview"),
)


@dataclass(frozen=True, slots=True)
class FirstPassClassification:
    lane: Lane
    stage_status: StageStatus
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]
    metadata_only: bool
    review_queue_needed: bool
    allowed_stages: AllowedStages
    local_llm_status: LocalLLMStatus = LocalLLMStatus.SKIPPED


def classify_document(
    document: DocumentClassificationInput,
    local_llm_adapter: LocalLLMAdapter | None = None,
) -> FirstPassClassification:
    safety_codes = _metadata_only_safety_codes(document)
    if safety_codes:
        return _build_decision(Lane.RED, safety_codes, LocalLLMStatus.SKIPPED)

    light_text_codes = _light_text_reason_codes(document)
    if light_text_codes:
        return _build_decision(Lane.RED, light_text_codes, LocalLLMStatus.SKIPPED)

    amber_codes = _amber_reason_codes(document)
    if amber_codes:
        return _build_decision(Lane.AMBER, amber_codes, LocalLLMStatus.SKIPPED)

    local_status = _local_llm_status(document, local_llm_adapter)
    return _build_decision(
        _metadata_lane(document.metadata.document_type_hint),
        _green_reason_codes(document),
        local_status,
    )


def _metadata_only_safety_codes(
    document: DocumentClassificationInput,
) -> tuple[str, ...]:
    codes: list[str] = []
    if document.traits.encrypted:
        codes.append("encrypted_pdf")
    if document.traits.corrupt:
        codes.append("corrupt_pdf")
    if document.traits.suspicious:
        codes.append("suspicious_file")
    if _path_contains(document, RESTRICTED_PATH_TOKENS):
        codes.append("restricted_path")
    return tuple(codes)


def _light_text_reason_codes(
    document: DocumentClassificationInput,
) -> tuple[str, ...]:
    if document.light_text_excerpt is None:
        return ()
    if _tokens(document.light_text_excerpt) & SENSITIVE_TEXT_TOKENS:
        return ("sensitive_excerpt",)
    return ()


def _amber_reason_codes(document: DocumentClassificationInput) -> tuple[str, ...]:
    codes: list[str] = []
    if document.traits.duplicate_conflict:
        codes.append("duplicate_conflict")
    if _path_contains(document, AMBER_PATH_TOKENS):
        codes.append("ambiguous_path")
    match document.metadata.document_type_hint:
        case DocumentTypeHint.PRESENTATION:
            codes.append("presentation_unknown")
        case DocumentTypeHint.UNKNOWN:
            codes.append("unknown_document_type")
        case DocumentTypeHint.RESEARCH_ARTICLE | DocumentTypeHint.OFFICIAL_REPORT:
            pass
        case unreachable:
            assert_never(unreachable)
    return tuple(codes)


def _metadata_lane(hint: DocumentTypeHint) -> Lane:
    match hint:
        case DocumentTypeHint.RESEARCH_ARTICLE | DocumentTypeHint.OFFICIAL_REPORT:
            return Lane.GREEN
        case DocumentTypeHint.PRESENTATION | DocumentTypeHint.UNKNOWN:
            return Lane.AMBER
        case unreachable:
            assert_never(unreachable)


def _green_reason_codes(document: DocumentClassificationInput) -> tuple[str, ...]:
    metadata_tokens = _metadata_tokens(document)
    if metadata_tokens & OFFICIAL_TEXT_TOKENS:
        return ("official_report",)
    if metadata_tokens & RESEARCH_TEXT_TOKENS:
        return ("research_article",)
    match document.metadata.document_type_hint:
        case DocumentTypeHint.RESEARCH_ARTICLE:
            return ("research_article",)
        case DocumentTypeHint.OFFICIAL_REPORT:
            return ("official_report",)
        case DocumentTypeHint.PRESENTATION | DocumentTypeHint.UNKNOWN:
            return ("needs_review",)
        case unreachable:
            assert_never(unreachable)


def _build_decision(
    lane: Lane,
    reason_codes: tuple[str, ...],
    local_llm_status: LocalLLMStatus,
) -> FirstPassClassification:
    return FirstPassClassification(
        lane=lane,
        stage_status=stage_status_for_lane(lane),
        reason_codes=reason_codes,
        reasons=tuple(_reason_text(code) for code in reason_codes),
        metadata_only=lane == Lane.RED,
        review_queue_needed=lane == Lane.AMBER,
        allowed_stages=allowed_stages_for_lane(lane),
        local_llm_status=local_llm_status,
    )


def _local_llm_status(
    document: DocumentClassificationInput,
    local_llm_adapter: LocalLLMAdapter | None,
) -> LocalLLMStatus:
    if local_llm_adapter is None:
        return LocalLLMStatus.SKIPPED
    result = local_llm_adapter.classify(local_llm_request_for(document))
    return result.status


def _path_contains(
    document: DocumentClassificationInput,
    expected_tokens: frozenset[str],
) -> bool:
    return bool(_tokens(document.path.as_posix()) & expected_tokens)


def _metadata_tokens(document: DocumentClassificationInput) -> set[str]:
    return _tokens(" ".join((document.metadata.title, *document.metadata.keywords)))


def _tokens(value: str) -> set[str]:
    return set(TOKEN_RE.findall(value.casefold()))


def _reason_text(reason_code: str) -> str:
    return reason_code.replace("_", " ")
