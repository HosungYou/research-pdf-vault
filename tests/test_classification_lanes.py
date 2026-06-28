from __future__ import annotations

import csv
import sys
from dataclasses import fields
from pathlib import Path
from typing import Final, assert_never

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
LANE_MATRIX: Final = ROOT / "fixtures" / "lanes" / "lane-matrix.csv"
EXPECTED_LOCAL_LLM_EXCERPT_LIMIT: Final = 1200
sys.path.insert(0, str(SCRIPTS_DIR))


def _case_rows() -> list[dict[str, str]]:
    with LANE_MATRIX.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _expected_bool(value: str) -> bool:
    return value == "true"


def _traits(raw: str) -> set[str]:
    if raw == "":
        return set()
    return set(raw.split(";"))


@pytest.mark.parametrize("row", _case_rows(), ids=lambda row: row["case_id"])
def test_lane_matrix_classifies_first_pass_decisions(row: dict[str, str]) -> None:
    from research_pdf_vault.classification import classify_document
    from research_pdf_vault.document_traits import (
        DocumentClassificationInput,
        DocumentMetadata,
        DocumentTraits,
        DocumentTypeHint,
    )
    from research_pdf_vault.schema import Lane, StageStatus

    # Given
    traits = _traits(row["traits"])
    document = DocumentClassificationInput(
        path=Path(row["path"]),
        metadata=DocumentMetadata(
            title=row["title"],
            document_type_hint=DocumentTypeHint(row["document_type_hint"]),
        ),
        traits=DocumentTraits(
            encrypted="encrypted" in traits,
            corrupt="corrupt" in traits,
            suspicious=False,
            duplicate_conflict="duplicate_conflict" in traits,
        ),
        light_text_excerpt=row["light_text_excerpt"],
    )

    # When
    decision = classify_document(document)

    # Then
    assert decision.lane == Lane(row["expected_lane"])
    assert decision.review_queue_needed is _expected_bool(row["expected_review_queue"])
    assert decision.metadata_only is _expected_bool(row["expected_metadata_only"])
    match decision.lane:
        case Lane.GREEN:
            assert decision.stage_status == StageStatus.COMPLETE
            assert decision.allowed_stages.can_vectorize is True
        case Lane.AMBER:
            assert decision.stage_status == StageStatus.PENDING
            assert decision.allowed_stages.can_vectorize is False
        case Lane.RED:
            assert decision.stage_status == StageStatus.QUARANTINED
            assert decision.allowed_stages.can_extract_text is False
        case unreachable:
            assert_never(unreachable)


def test_disabled_local_llm_adapter_receives_only_bounded_request_contract() -> None:
    from research_pdf_vault.classification import classify_document
    from research_pdf_vault.document_traits import (
        DisabledLocalLLMAdapter,
        DocumentClassificationInput,
        DocumentMetadata,
        DocumentTraits,
        DocumentTypeHint,
        LocalLLMAdapter,
        LocalLLMRequest,
        LocalLLMResult,
        LocalLLMStatus,
    )
    from research_pdf_vault.schema import Lane

    class CapturingLocalLLMAdapter:
        def __init__(self) -> None:
            self.requests: list[LocalLLMRequest] = []

        def classify(self, request: LocalLLMRequest) -> LocalLLMResult:
            self.requests.append(request)
            return DisabledLocalLLMAdapter().classify(request)

    # Given
    capturing_adapter = CapturingLocalLLMAdapter()
    adapter: LocalLLMAdapter = capturing_adapter
    long_excerpt = "Official published findings. " * 200
    document = DocumentClassificationInput(
        path=Path("fixtures/classification/green/official-report.pdf"),
        metadata=DocumentMetadata(
            title="Synthetic Official Report",
            document_type_hint=DocumentTypeHint.OFFICIAL_REPORT,
        ),
        traits=DocumentTraits(),
        light_text_excerpt=long_excerpt,
    )

    # When
    decision = classify_document(document, local_llm_adapter=adapter)
    disabled_result = DisabledLocalLLMAdapter().classify(capturing_adapter.requests[0])

    # Then
    request_field_names = {field.name for field in fields(LocalLLMRequest)}
    result_field_names = {field.name for field in fields(LocalLLMResult)}
    assert all("full_text" not in field_name for field_name in request_field_names)
    assert all("full_text" not in field_name for field_name in result_field_names)
    assert capturing_adapter.requests == [
        LocalLLMRequest(
            path=document.path,
            metadata=document.metadata,
            light_text_excerpt=long_excerpt[:EXPECTED_LOCAL_LLM_EXCERPT_LIMIT],
        ),
    ]
    assert disabled_result.status == LocalLLMStatus.DISABLED
    assert disabled_result.lane is None
    assert decision.lane == Lane.GREEN
    assert decision.local_llm_status == LocalLLMStatus.DISABLED
