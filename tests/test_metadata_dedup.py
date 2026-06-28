from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from research_pdf_vault.dedup import CandidateId, PaperCandidate, deduplicate_papers
from research_pdf_vault.fingerprint import text_fingerprint
from research_pdf_vault.metadata import RawPaperMetadata, normalize_metadata
from research_pdf_vault.schema import Lane, RepoRelativePath, Sha256Hex


def test_normalize_metadata_when_identifier_variants_then_canonical_values() -> None:
    # Given
    metadata = RawPaperMetadata(
        doi=" https://doi.org/10.1000/ABC.Def. ",
        isbn=" ISBN 978-1-4028-9462-6 ",
        arxiv_id="arXiv:2401.12345v2",
        title="  A   Synthetic Study:  On Deduplication ",
        authors=(" Ada  Lovelace ", "ALAN M. TURING"),
        year=2026,
    )

    # When
    normalized = normalize_metadata(metadata)

    # Then
    assert normalized.doi == "10.1000/abc.def"
    assert normalized.isbn == "9781402894626"
    assert normalized.arxiv_id == "2401.12345"
    assert normalized.title == "a synthetic study on deduplication"
    assert normalized.authors == ("ada lovelace", "alan m turing")
    assert normalized.year == 2026


def test_text_fingerprint_when_whitespace_and_case_differ_then_digest_matches() -> None:
    # Given
    first_text = "Methods\n\nWe compare layered DEDUP rules."
    second_text = " methods we compare layered dedup rules "

    # When
    first = text_fingerprint(first_text)
    second = text_fingerprint(second_text)

    # Then
    assert first == second
    assert len(first) == 64


def test_deduplicate_papers_when_same_doi_then_one_paper_with_two_instances() -> None:
    # Given
    candidates = (
        PaperCandidate(
            candidate_id=CandidateId("record_a"),
            file_path=RepoRelativePath("library/alpha.pdf"),
            sha256=Sha256Hex("a" * 64),
            metadata=RawPaperMetadata(
                doi="10.5555/SAME.DOI",
                title="Layered Dedup",
                authors=("Ada Lovelace",),
                year=2026,
            ),
            extracted_text="Layered dedup study body A.",
        ),
        PaperCandidate(
            candidate_id=CandidateId("record_b"),
            file_path=RepoRelativePath("library/beta.pdf"),
            sha256=Sha256Hex("b" * 64),
            metadata=RawPaperMetadata(
                doi="https://doi.org/10.5555/same.doi",
                title="Layered Dedup",
                authors=("Ada Lovelace",),
                year=2026,
            ),
            extracted_text="Layered dedup study body B.",
        ),
    )

    # When
    result = deduplicate_papers(candidates)

    # Then
    paper_ids = {assignment.paper_id for assignment in result.paper_assignments}
    assert len(paper_ids) == 1
    assert len(result.paper_instances) == 2
    assert {instance.paper_id for instance in result.paper_instances} == paper_ids
    assert result.merge_candidates == ()


def test_deduplicate_papers_when_doi_conflicts_then_lower_keys_do_not_merge() -> None:
    # Given
    candidates = (
        PaperCandidate(
            candidate_id=CandidateId("doi_left"),
            file_path=RepoRelativePath("library/doi-left.pdf"),
            sha256=Sha256Hex("1" * 64),
            metadata=RawPaperMetadata(
                doi="10.7000/left",
                title="Shared Citation",
                authors=("Ada Lovelace",),
                year=2026,
            ),
            extracted_text="Left unique text.",
        ),
        PaperCandidate(
            candidate_id=CandidateId("doi_right"),
            file_path=RepoRelativePath("library/doi-right.pdf"),
            sha256=Sha256Hex("2" * 64),
            metadata=RawPaperMetadata(
                doi="10.7000/right",
                title="Shared Citation",
                authors=("Ada Lovelace",),
                year=2026,
            ),
            extracted_text="Right unique text.",
        ),
    )

    # When
    result = deduplicate_papers(candidates)

    # Then
    assert len({assignment.paper_id for assignment in result.paper_assignments}) == 2
    assert len(result.merge_candidates) == 1
    merge = result.merge_candidates[0]
    assert merge.lane is Lane.AMBER
    assert merge.requires_audited_decision is True
    assert merge.candidate_ids == (CandidateId("doi_left"), CandidateId("doi_right"))


def test_deduplicate_papers_when_title_year_conflicting_authors_then_amber_review() -> None:
    # Given
    candidates = (
        PaperCandidate(
            candidate_id=CandidateId("record_left"),
            file_path=RepoRelativePath("library/left.pdf"),
            sha256=Sha256Hex("c" * 64),
            metadata=RawPaperMetadata(
                title="Same Title",
                authors=("Ada Lovelace",),
                year=2026,
            ),
            extracted_text="Left paper body.",
        ),
        PaperCandidate(
            candidate_id=CandidateId("record_right"),
            file_path=RepoRelativePath("library/right.pdf"),
            sha256=Sha256Hex("d" * 64),
            metadata=RawPaperMetadata(
                title="Same   Title",
                authors=("Alan Turing",),
                year=2026,
            ),
            extracted_text="Right paper body.",
        ),
    )

    # When
    result = deduplicate_papers(candidates)

    # Then
    assert len({assignment.paper_id for assignment in result.paper_assignments}) == 2
    assert len(result.merge_candidates) == 1
    merge = result.merge_candidates[0]
    assert merge.lane is Lane.AMBER
    assert merge.requires_audited_decision is True
    assert merge.candidate_ids == (CandidateId("record_left"), CandidateId("record_right"))


def test_deduplicate_papers_when_no_identifiers_then_text_fingerprint_groups() -> None:
    # Given
    candidates = (
        PaperCandidate(
            candidate_id=CandidateId("record_text_a"),
            file_path=RepoRelativePath("library/random-name-a.pdf"),
            sha256=Sha256Hex("e" * 64),
            metadata=RawPaperMetadata(),
            extracted_text="A synthetic paper body with stable full text.",
        ),
        PaperCandidate(
            candidate_id=CandidateId("record_text_b"),
            file_path=RepoRelativePath("library/random-name-b.pdf"),
            sha256=Sha256Hex("f" * 64),
            metadata=RawPaperMetadata(),
            extracted_text=" a synthetic paper body with stable full text ",
        ),
    )

    # When
    result = deduplicate_papers(candidates)

    # Then
    assert len({assignment.paper_id for assignment in result.paper_assignments}) == 1
    assert len(result.paper_instances) == 2
    assert result.unassigned_candidates == ()


def test_deduplicate_papers_when_only_paths_exist_then_path_is_not_identity() -> None:
    # Given
    candidates = (
        PaperCandidate(
            candidate_id=CandidateId("path_a"),
            file_path=RepoRelativePath("library/a.pdf"),
            sha256=None,
            metadata=RawPaperMetadata(),
            extracted_text=None,
        ),
        PaperCandidate(
            candidate_id=CandidateId("path_b"),
            file_path=RepoRelativePath("library/b.pdf"),
            sha256=None,
            metadata=RawPaperMetadata(),
            extracted_text=None,
        ),
    )

    # When
    result = deduplicate_papers(candidates)

    # Then
    assert result.paper_assignments == ()
    assert result.paper_instances == ()
    assert len(result.unassigned_candidates) == 2
