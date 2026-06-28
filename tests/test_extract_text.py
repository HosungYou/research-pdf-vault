from __future__ import annotations

import sys
import typing
import importlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
EXTRACTION_FIXTURES: Final = ROOT / "fixtures" / "extraction"
sys.path.insert(0, str(SCRIPTS_DIR))
OcrPageRequest = importlib.import_module("research_pdf_vault.ocr").OcrPageRequest


@dataclass(frozen=True, slots=True)
class SafetyFixtureCase:
    fixture_name: str
    encrypted: bool
    corrupt: bool
    reason_code: str


class FakeOcrAdapter:
    def __init__(self, responses: Mapping[int, str]) -> None:
        self.responses = responses
        self.requests: list[OcrPageRequest] = []

    def extract_page_text(self, request: OcrPageRequest) -> str:
        self.requests.append(request)
        return self.responses[request.page]


def test_runtime_type_hints_resolve_for_extraction_and_fake_ocr_adapter() -> None:
    import research_pdf_vault.extraction as extraction
    from research_pdf_vault.ocr import OcrPageRequest

    # Given / When
    module_hints = typing.get_type_hints(extraction)
    method_hints = typing.get_type_hints(FakeOcrAdapter.extract_page_text)

    # Then
    assert "DEFAULT_EXTRACTION_POLICY" in module_hints
    assert method_hints == {"request": OcrPageRequest, "return": str}


def test_green_text_pdf_extracts_text_pages_and_writes_artifact(tmp_path: Path) -> None:
    from research_pdf_vault.document_traits import DocumentTraits
    from research_pdf_vault.extraction import (
        DEFAULT_EXTRACTION_POLICY,
        ExtractionMethod,
        TextExtractionRequest,
        extract_text,
    )
    from research_pdf_vault.schema import InstanceId, Lane, PaperId, StageStatus

    # Given
    artifact_dir = tmp_path / "artifacts"
    request = TextExtractionRequest(
        source_path=EXTRACTION_FIXTURES / "happy" / "synthetic-text.pdf",
        paper_id=PaperId("paper-green"),
        instance_id=InstanceId("instance-green"),
        lane=Lane.GREEN,
        traits=DocumentTraits(),
        artifact_dir=artifact_dir,
    )

    # When
    result = extract_text(request, policy=DEFAULT_EXTRACTION_POLICY)

    # Then
    assert result.status.stage_status == StageStatus.COMPLETE
    assert result.status.method == ExtractionMethod.TEXT
    assert result.status.ocr_status.value == "not_needed"
    assert result.status.text_artifact_path == artifact_dir / "instance-green.txt"
    assert result.status.text_artifact_path.read_text(encoding="utf-8").startswith(
        "Synthetic Green report page one.",
    )
    assert [page.source_location.page for page in result.pages] == [1, 2]
    assert result.pages[0].source_location.start_offset == 0
    assert result.pages[0].source_location.end_offset == len(result.pages[0].text)
    assert "Second page includes methods" in result.pages[1].text
    assert result.audit_entries == ()


def test_green_scanned_pdf_uses_fake_ocr_adapter_when_policy_allows(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.document_traits import DocumentTraits
    from research_pdf_vault.extraction import (
        DEFAULT_EXTRACTION_POLICY,
        ExtractionMethod,
        TextExtractionRequest,
        extract_text,
    )
    from research_pdf_vault.ocr import OcrStatus
    from research_pdf_vault.schema import InstanceId, Lane, PaperId, StageStatus

    # Given
    fake_ocr = FakeOcrAdapter(
        {
            1: "OCR page one text.",
            2: "OCR page two text.",
        },
    )
    request = TextExtractionRequest(
        source_path=EXTRACTION_FIXTURES / "ocr" / "scanned-empty.pdf",
        paper_id=PaperId("paper-scan"),
        instance_id=InstanceId("instance-scan"),
        lane=Lane.GREEN,
        traits=DocumentTraits(),
        artifact_dir=tmp_path / "artifacts",
    )

    # When
    result = extract_text(
        request,
        policy=DEFAULT_EXTRACTION_POLICY,
        ocr_adapter=fake_ocr,
    )

    # Then
    assert result.status.stage_status == StageStatus.COMPLETE
    assert result.status.method == ExtractionMethod.OCR
    assert result.status.ocr_status == OcrStatus.COMPLETE
    assert [ocr_request.page for ocr_request in fake_ocr.requests] == [1, 2]
    assert result.pages[0].text == "OCR page one text."
    assert result.pages[1].source_location.page == 2
    assert result.status.text_artifact_path is not None
    assert "OCR page two text." in result.status.text_artifact_path.read_text(
        encoding="utf-8",
    )


def test_red_fixture_produces_no_text_artifact_and_audit_entry(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.document_traits import DocumentTraits
    from research_pdf_vault.extraction import (
        DEFAULT_EXTRACTION_POLICY,
        ExtractionMethod,
        TextExtractionRequest,
        extract_text,
    )
    from research_pdf_vault.ocr import OcrStatus
    from research_pdf_vault.schema import InstanceId, Lane, PaperId, StageStatus

    # Given
    request = TextExtractionRequest(
        source_path=EXTRACTION_FIXTURES / "failure" / "red-sensitive.pdf",
        paper_id=PaperId("paper-red"),
        instance_id=InstanceId("instance-red"),
        lane=Lane.RED,
        traits=DocumentTraits(),
        artifact_dir=tmp_path / "artifacts",
    )

    # When
    result = extract_text(request, policy=DEFAULT_EXTRACTION_POLICY)

    # Then
    assert result.status.stage_status == StageStatus.QUARANTINED
    assert result.status.method == ExtractionMethod.NONE
    assert result.status.ocr_status == OcrStatus.BLOCKED
    assert result.pages == ()
    assert result.status.text_artifact_path is None
    assert not (tmp_path / "artifacts").exists()
    assert [entry.reason_code for entry in result.audit_entries] == ["red_lane_blocked"]


@pytest.mark.parametrize(
    "case",
    (
        SafetyFixtureCase(
            fixture_name="encrypted.pdf",
            encrypted=True,
            corrupt=False,
            reason_code="encrypted_pdf_blocked",
        ),
        SafetyFixtureCase(
            fixture_name="corrupt.pdf",
            encrypted=False,
            corrupt=True,
            reason_code="corrupt_pdf_blocked",
        ),
    ),
    ids=lambda case: case.fixture_name.removesuffix(".pdf"),
)
def test_encrypted_or_corrupt_fixture_produces_no_text_artifact_and_audit_entry(
    case: SafetyFixtureCase,
    tmp_path: Path,
) -> None:
    from research_pdf_vault.document_traits import DocumentTraits
    from research_pdf_vault.extraction import (
        DEFAULT_EXTRACTION_POLICY,
        ExtractionMethod,
        TextExtractionRequest,
        extract_text,
    )
    from research_pdf_vault.ocr import OcrStatus
    from research_pdf_vault.schema import InstanceId, Lane, PaperId, StageStatus

    # Given
    request = TextExtractionRequest(
        source_path=EXTRACTION_FIXTURES / "failure" / case.fixture_name,
        paper_id=PaperId(f"paper-{case.fixture_name}"),
        instance_id=InstanceId(f"instance-{case.fixture_name}"),
        lane=Lane.GREEN,
        traits=DocumentTraits(
            encrypted=case.encrypted,
            corrupt=case.corrupt,
        ),
        artifact_dir=tmp_path / "artifacts",
    )

    # When
    result = extract_text(request, policy=DEFAULT_EXTRACTION_POLICY)

    # Then
    assert result.status.stage_status == StageStatus.FAILED
    assert result.status.method == ExtractionMethod.NONE
    assert result.status.ocr_status == OcrStatus.BLOCKED
    assert result.pages == ()
    assert result.status.text_artifact_path is None
    assert not (tmp_path / "artifacts").exists()
    assert [entry.reason_code for entry in result.audit_entries] == [case.reason_code]
