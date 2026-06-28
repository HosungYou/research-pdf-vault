from __future__ import annotations

from pathlib import Path
from typing import Final, assert_never

from research_pdf_vault.document_traits import DocumentTraits
from research_pdf_vault.ocr import OcrAdapter, OcrPageRequest, OcrStatus
from research_pdf_vault.ocr_policy import (
    DEFAULT_OCR_POLICY,
    OcrPolicy,
    OcrPolicyRequest,
    ocr_policy_decision,
)
from research_pdf_vault.extraction_types import (
    ExtractedTextPage,
    ExtractionAuditEntry,
    ExtractionMethod,
    ExtractionPolicy,
    ExtractionResult,
    ExtractionStatusRecord,
    TextExtractionRequest,
)
from research_pdf_vault.schema import Lane, StageStatus
from research_pdf_vault.synthetic_pdf import (
    page_from_text,
    pdf_block_reason,
    synthetic_scanned_pages,
    synthetic_text_pages,
)


DEFAULT_EXTRACTION_POLICY: Final = ExtractionPolicy(ocr_policy=DEFAULT_OCR_POLICY)


def extract_text(
    request: TextExtractionRequest,
    policy: ExtractionPolicy = DEFAULT_EXTRACTION_POLICY,
    ocr_adapter: OcrAdapter | None = None,
) -> ExtractionResult:
    lane_block = _lane_block_reason(request.lane)
    if lane_block is not None:
        return _blocked_result(request, StageStatus.QUARANTINED, lane_block)
    safety_block = _safety_block_reason(request.traits)
    if safety_block is not None:
        return _blocked_result(request, StageStatus.FAILED, safety_block)
    data = request.source_path.read_bytes()
    pdf_block = pdf_block_reason(data)
    if pdf_block is not None:
        return _blocked_result(request, StageStatus.FAILED, pdf_block)
    text_pages = synthetic_text_pages(data)
    if text_pages:
        return _complete_result(request, text_pages, ExtractionMethod.TEXT, OcrStatus.NOT_NEEDED)
    scanned_pages = synthetic_scanned_pages(data)
    return _ocr_result(request, policy.ocr_policy, ocr_adapter, scanned_pages)


def _lane_block_reason(lane: Lane) -> str | None:
    match lane:
        case Lane.GREEN | Lane.AMBER:
            return None
        case Lane.RED:
            return "red_lane_blocked"
        case unreachable:
            assert_never(unreachable)


def _safety_block_reason(traits: DocumentTraits) -> str | None:
    if traits.encrypted:
        return "encrypted_pdf_blocked"
    if traits.corrupt:
        return "corrupt_pdf_blocked"
    return None


def _ocr_result(
    request: TextExtractionRequest,
    policy: OcrPolicy,
    ocr_adapter: OcrAdapter | None,
    scanned_pages: tuple[int, ...],
) -> ExtractionResult:
    decision = ocr_policy_decision(
        OcrPolicyRequest(lane=request.lane, traits=request.traits, policy=policy),
    )
    if not decision.allowed:
        return _blocked_result(request, StageStatus.FAILED, decision.reason_code)
    if ocr_adapter is None:
        return _failed_result(request, OcrStatus.SKIPPED, "ocr_adapter_missing")
    pages = tuple(
        page_from_text(
            page_number,
            ocr_adapter.extract_page_text(
                OcrPageRequest(
                    source_path=request.source_path,
                    page=page_number,
                    constrained=decision.constrained,
                    max_chars=decision.max_chars,
                ),
            )[: decision.max_chars].strip(),
        )
        for page_number in scanned_pages
    )
    extracted_pages = tuple(page for page in pages if page.text)
    if extracted_pages:
        return _complete_result(
            request,
            extracted_pages,
            ExtractionMethod.OCR,
            OcrStatus.COMPLETE,
        )
    return _failed_result(request, OcrStatus.FAILED, "ocr_produced_no_text")


def _complete_result(
    request: TextExtractionRequest,
    pages: tuple[ExtractedTextPage, ...],
    method: ExtractionMethod,
    ocr_status: OcrStatus,
) -> ExtractionResult:
    artifact_path = _write_text_artifact(request, pages)
    return ExtractionResult(
        status=ExtractionStatusRecord(
            stage_status=StageStatus.COMPLETE,
            method=method,
            ocr_status=ocr_status,
            page_count=len(pages),
            char_count=sum(len(page.text) for page in pages),
            text_artifact_path=artifact_path,
            reason_codes=(),
        ),
        pages=pages,
        audit_entries=(),
    )


def _blocked_result(
    request: TextExtractionRequest,
    stage_status: StageStatus,
    reason_code: str,
) -> ExtractionResult:
    return ExtractionResult(
        status=ExtractionStatusRecord(
            stage_status=stage_status,
            method=ExtractionMethod.NONE,
            ocr_status=OcrStatus.BLOCKED,
            page_count=0,
            char_count=0,
            text_artifact_path=None,
            reason_codes=(reason_code,),
        ),
        pages=(),
        audit_entries=(_audit_entry(request, stage_status, reason_code),),
    )


def _failed_result(
    request: TextExtractionRequest,
    ocr_status: OcrStatus,
    reason_code: str,
) -> ExtractionResult:
    return ExtractionResult(
        status=ExtractionStatusRecord(
            stage_status=StageStatus.FAILED,
            method=ExtractionMethod.NONE,
            ocr_status=ocr_status,
            page_count=0,
            char_count=0,
            text_artifact_path=None,
            reason_codes=(reason_code,),
        ),
        pages=(),
        audit_entries=(_audit_entry(request, StageStatus.FAILED, reason_code),),
    )


def _audit_entry(
    request: TextExtractionRequest,
    stage_status: StageStatus,
    reason_code: str,
) -> ExtractionAuditEntry:
    return ExtractionAuditEntry(
        paper_id=request.paper_id,
        instance_id=request.instance_id,
        lane=request.lane,
        stage_status=stage_status,
        reason_code=reason_code,
        message=reason_code.replace("_", " "),
    )


def _write_text_artifact(
    request: TextExtractionRequest,
    pages: tuple[ExtractedTextPage, ...],
) -> Path | None:
    if request.artifact_dir is None:
        return None
    request.artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = request.artifact_dir / f"{request.instance_id}.txt"
    artifact_path.write_text(
        "\n\n".join(page.text for page in pages),
        encoding="utf-8",
    )
    return artifact_path
