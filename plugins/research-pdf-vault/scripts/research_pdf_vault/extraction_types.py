from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique
from pathlib import Path

from research_pdf_vault.document_traits import DocumentTraits
from research_pdf_vault.ocr import OcrStatus
from research_pdf_vault.ocr_policy import OcrPolicy
from research_pdf_vault.schema import InstanceId, Lane, PaperId, SourceLocation, StageStatus


@unique
class ExtractionMethod(StrEnum):
    TEXT = "text"
    OCR = "ocr"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ExtractionPolicy:
    ocr_policy: OcrPolicy


@dataclass(frozen=True, slots=True)
class TextExtractionRequest:
    source_path: Path
    paper_id: PaperId
    instance_id: InstanceId
    lane: Lane
    traits: DocumentTraits
    artifact_dir: Path | None = None


@dataclass(frozen=True, slots=True)
class ExtractedTextPage:
    source_location: SourceLocation
    text: str


@dataclass(frozen=True, slots=True)
class ExtractionAuditEntry:
    paper_id: PaperId
    instance_id: InstanceId
    lane: Lane
    stage_status: StageStatus
    reason_code: str
    message: str


@dataclass(frozen=True, slots=True)
class ExtractionStatusRecord:
    stage_status: StageStatus
    method: ExtractionMethod
    ocr_status: OcrStatus
    page_count: int
    char_count: int
    text_artifact_path: Path | None
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    status: ExtractionStatusRecord
    pages: tuple[ExtractedTextPage, ...]
    audit_entries: tuple[ExtractionAuditEntry, ...]
