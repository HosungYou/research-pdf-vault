from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique
from pathlib import Path
from typing import Final, Protocol

from research_pdf_vault.schema import Lane

LOCAL_LLM_EXCERPT_CHAR_LIMIT: Final = 1200


@unique
class DocumentTypeHint(StrEnum):
    RESEARCH_ARTICLE = "research_article"
    OFFICIAL_REPORT = "official_report"
    PRESENTATION = "presentation"
    UNKNOWN = "unknown"


@unique
class LocalLLMStatus(StrEnum):
    DISABLED = "disabled"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    title: str
    document_type_hint: DocumentTypeHint = DocumentTypeHint.UNKNOWN
    keywords: tuple[str, ...] = ()
    producer: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentTraits:
    encrypted: bool = False
    corrupt: bool = False
    suspicious: bool = False
    duplicate_conflict: bool = False


@dataclass(frozen=True, slots=True)
class DocumentClassificationInput:
    path: Path
    metadata: DocumentMetadata
    traits: DocumentTraits
    light_text_excerpt: str | None = None


@dataclass(frozen=True, slots=True)
class LocalLLMRequest:
    path: Path
    metadata: DocumentMetadata
    light_text_excerpt: str | None


@dataclass(frozen=True, slots=True)
class LocalLLMResult:
    status: LocalLLMStatus
    lane: Lane | None = None
    reason_codes: tuple[str, ...] = ()


class LocalLLMAdapter(Protocol):
    def classify(self, request: LocalLLMRequest) -> LocalLLMResult:
        ...


@dataclass(frozen=True, slots=True)
class DisabledLocalLLMAdapter:
    def classify(self, request: LocalLLMRequest) -> LocalLLMResult:
        return LocalLLMResult(status=LocalLLMStatus.DISABLED)


def local_llm_request_for(document: DocumentClassificationInput) -> LocalLLMRequest:
    return LocalLLMRequest(
        path=document.path,
        metadata=document.metadata,
        light_text_excerpt=_bounded_excerpt(document.light_text_excerpt),
    )


def _bounded_excerpt(excerpt: str | None) -> str | None:
    if excerpt is None:
        return None
    return excerpt[:LOCAL_LLM_EXCERPT_CHAR_LIMIT]
