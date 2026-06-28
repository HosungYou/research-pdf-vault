from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def test_irb_student_sensitive_document_enters_red_metadata_only_quarantine() -> None:
    from research_pdf_vault.classification import classify_document
    from research_pdf_vault.document_traits import (
        DocumentClassificationInput,
        DocumentMetadata,
        DocumentTraits,
        DocumentTypeHint,
    )
    from research_pdf_vault.quarantine import quarantine_policy_for
    from research_pdf_vault.schema import Lane, StageStatus

    # Given
    document = DocumentClassificationInput(
        path=Path("fixtures/classification/private/student-irb-notes.pdf"),
        metadata=DocumentMetadata(
            title="Synthetic Participant Notes",
            document_type_hint=DocumentTypeHint.UNKNOWN,
        ),
        traits=DocumentTraits(),
        light_text_excerpt="IRB protocol student participant consent notes.",
    )

    # When
    decision = classify_document(document)
    policy = quarantine_policy_for(decision)

    # Then
    assert decision.lane == Lane.RED
    assert decision.stage_status == StageStatus.QUARANTINED
    assert decision.metadata_only is True
    assert decision.review_queue_needed is False
    assert policy.quarantine_required is True
    assert policy.allowed_stages.can_extract_text is False
    assert policy.allowed_stages.can_ocr is False
    assert policy.allowed_stages.can_vectorize is False


@pytest.mark.parametrize(
    "path,traits",
    (
        (
            Path("fixtures/classification/red/encrypted.pdf"),
            {"encrypted"},
        ),
        (
            Path("fixtures/classification/red/corrupt.pdf"),
            {"corrupt"},
        ),
        (
            Path("fixtures/classification/restricted/research.pdf"),
            set(),
        ),
    ),
    ids=("encrypted", "corrupt", "restricted-path"),
)
def test_red_safety_cases_block_text_ocr_and_vector_jobs(
    path: Path,
    traits: set[str],
) -> None:
    from research_pdf_vault.classification import classify_document
    from research_pdf_vault.document_traits import (
        DocumentClassificationInput,
        DocumentMetadata,
        DocumentTraits,
        DocumentTypeHint,
    )
    from research_pdf_vault.schema import Lane

    # Given
    document = DocumentClassificationInput(
        path=path,
        metadata=DocumentMetadata(
            title="Synthetic Safety Case",
            document_type_hint=DocumentTypeHint.OFFICIAL_REPORT,
        ),
        traits=DocumentTraits(
            encrypted="encrypted" in traits,
            corrupt="corrupt" in traits,
        ),
        light_text_excerpt="Official public report language that must not override safety.",
    )

    # When
    decision = classify_document(document)

    # Then
    assert decision.lane == Lane.RED
    assert decision.metadata_only is True
    assert decision.allowed_stages.can_extract_text is False
    assert decision.allowed_stages.can_ocr is False
    assert decision.allowed_stages.can_vectorize is False


def test_restricted_path_is_classified_before_light_text_is_considered() -> None:
    from research_pdf_vault.classification import classify_document
    from research_pdf_vault.document_traits import (
        DocumentClassificationInput,
        DocumentMetadata,
        DocumentTraits,
        DocumentTypeHint,
    )
    from research_pdf_vault.schema import Lane

    # Given
    document = DocumentClassificationInput(
        path=Path("fixtures/classification/restricted/official-report.pdf"),
        metadata=DocumentMetadata(
            title="Synthetic Official Report",
            document_type_hint=DocumentTypeHint.OFFICIAL_REPORT,
        ),
        traits=DocumentTraits(),
        light_text_excerpt="Official annual report with public findings.",
    )

    # When
    decision = classify_document(document)

    # Then
    assert decision.lane == Lane.RED
    assert decision.metadata_only is True
    assert decision.reason_codes == ("restricted_path",)


def test_sensitive_light_text_enters_red_when_path_allows_excerpt_use() -> None:
    from research_pdf_vault.classification import classify_document
    from research_pdf_vault.document_traits import (
        DocumentClassificationInput,
        DocumentMetadata,
        DocumentTraits,
        DocumentTypeHint,
    )
    from research_pdf_vault.schema import Lane

    # Given
    document = DocumentClassificationInput(
        path=Path("fixtures/classification/red/participant-notes.pdf"),
        metadata=DocumentMetadata(
            title="Synthetic Participant Notes",
            document_type_hint=DocumentTypeHint.UNKNOWN,
        ),
        traits=DocumentTraits(),
        light_text_excerpt="IRB protocol student participant consent notes.",
    )

    # When
    decision = classify_document(document)

    # Then
    assert decision.lane == Lane.RED
    assert decision.metadata_only is True
    assert decision.reason_codes == ("sensitive_excerpt",)


def test_duplicate_conflict_enters_amber_review_without_auto_merge() -> None:
    from research_pdf_vault.classification import classify_document
    from research_pdf_vault.document_traits import (
        DocumentClassificationInput,
        DocumentMetadata,
        DocumentTraits,
        DocumentTypeHint,
    )
    from research_pdf_vault.schema import Lane, StageStatus

    # Given
    document = DocumentClassificationInput(
        path=Path("fixtures/classification/amber/research-copy.pdf"),
        metadata=DocumentMetadata(
            title="Synthetic Duplicate",
            document_type_hint=DocumentTypeHint.RESEARCH_ARTICLE,
        ),
        traits=DocumentTraits(duplicate_conflict=True),
        light_text_excerpt="Abstract Methods Results Discussion.",
    )

    # When
    decision = classify_document(document)

    # Then
    assert decision.lane == Lane.AMBER
    assert decision.stage_status == StageStatus.PENDING
    assert decision.review_queue_needed is True
    assert decision.allowed_stages.can_vectorize is False
    assert "duplicate_conflict" in decision.reason_codes
