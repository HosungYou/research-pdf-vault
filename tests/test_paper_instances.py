from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from research_pdf_vault.dedup import CandidateId, PaperCandidate, deduplicate_papers
from research_pdf_vault.identity import IdentityKind, ManifestPaper, PaperManifest
from research_pdf_vault.metadata import RawPaperMetadata
from research_pdf_vault.schema import Lane, PaperId, RepoRelativePath, Sha256Hex


def test_paper_assignment_when_path_moves_then_stored_paper_id_is_reused() -> None:
    # Given
    existing_paper_id = PaperId("paper_manifest_existing_001")
    original = PaperCandidate(
        candidate_id=CandidateId("record_original"),
        file_path=RepoRelativePath("library/original.pdf"),
        sha256=Sha256Hex("1" * 64),
        metadata=RawPaperMetadata(
            doi="10.4242/stable",
            title="Stable Identity",
            authors=("Ada Lovelace",),
            year=2026,
        ),
        extracted_text="Stable identity body.",
    )
    first_result = deduplicate_papers((original,))
    manifest = PaperManifest(
        papers=(
            ManifestPaper(
                paper_id=existing_paper_id,
                identity_keys=first_result.paper_assignments[0].identity_keys,
            ),
        ),
    )
    moved = PaperCandidate(
        candidate_id=CandidateId("record_original"),
        file_path=RepoRelativePath("library/moved/renamed.pdf"),
        sha256=Sha256Hex("1" * 64),
        metadata=RawPaperMetadata(
            doi="https://doi.org/10.4242/STABLE",
            title="Stable Identity",
            authors=("Ada Lovelace",),
            year=2026,
        ),
        extracted_text="Stable identity body.",
    )

    # When
    moved_result = deduplicate_papers((moved,), manifest)

    # Then
    assert moved_result.paper_assignments[0].paper_id == existing_paper_id
    assert moved_result.paper_instances[0].paper_id == existing_paper_id
    assert moved_result.paper_instances[0].file_path == RepoRelativePath(
        "library/moved/renamed.pdf",
    )


def test_paper_assignment_when_manifest_keys_have_different_owners_then_amber_review() -> None:
    # Given
    candidate = PaperCandidate(
        candidate_id=CandidateId("manifest_conflict"),
        file_path=RepoRelativePath("library/manifest-conflict.pdf"),
        sha256=Sha256Hex("6" * 64),
        metadata=RawPaperMetadata(
            doi="10.5151/conflict",
            title="Manifest Conflict",
            authors=("Ada Lovelace",),
            year=2026,
        ),
        extracted_text="Manifest conflict body.",
    )
    initial = deduplicate_papers((candidate,))
    identity_keys = initial.paper_assignments[0].identity_keys
    doi_keys = frozenset(key for key in identity_keys if key.kind is IdentityKind.DOI)
    citation_keys = frozenset(
        key for key in identity_keys if key.kind is IdentityKind.CITATION
    )
    existing_ids = {
        PaperId("paper_existing_doi_owner"),
        PaperId("paper_existing_citation_owner"),
    }
    manifest = PaperManifest(
        papers=(
            ManifestPaper(
                paper_id=PaperId("paper_existing_doi_owner"),
                identity_keys=doi_keys,
            ),
            ManifestPaper(
                paper_id=PaperId("paper_existing_citation_owner"),
                identity_keys=citation_keys,
            ),
        ),
    )

    # When
    result = deduplicate_papers((candidate,), manifest)

    # Then
    assignment = result.paper_assignments[0]
    assert assignment.paper_id not in existing_ids
    assert len(result.merge_candidates) == 1
    merge = result.merge_candidates[0]
    assert merge.lane is Lane.AMBER
    assert merge.requires_audited_decision is True
    assert existing_ids < set(merge.paper_ids)
    assert assignment.paper_id in merge.paper_ids


def test_paper_instances_when_same_identity_then_each_file_gets_own_instance() -> None:
    # Given
    candidates = (
        PaperCandidate(
            candidate_id=CandidateId("copy_one"),
            file_path=RepoRelativePath("library/copy-one.pdf"),
            sha256=Sha256Hex("2" * 64),
            metadata=RawPaperMetadata(arxiv_id="arXiv:2601.00001v3"),
            extracted_text="Copy one text.",
        ),
        PaperCandidate(
            candidate_id=CandidateId("copy_two"),
            file_path=RepoRelativePath("library/copy-two.pdf"),
            sha256=Sha256Hex("3" * 64),
            metadata=RawPaperMetadata(arxiv_id="2601.00001"),
            extracted_text="Copy two text.",
        ),
    )

    # When
    result = deduplicate_papers(candidates)

    # Then
    assert len(result.paper_instances) == 2
    assert result.paper_instances[0].instance_id != result.paper_instances[1].instance_id
    assert result.paper_instances[0].paper_id == result.paper_instances[1].paper_id


def test_merge_candidates_when_uncertain_then_require_audit_without_mutation() -> None:
    # Given
    candidates = (
        PaperCandidate(
            candidate_id=CandidateId("uncertain_one"),
            file_path=RepoRelativePath("library/uncertain-one.pdf"),
            sha256=Sha256Hex("4" * 64),
            metadata=RawPaperMetadata(
                title="Ambiguous Paper",
                authors=("Ada Lovelace",),
                year=2026,
            ),
            extracted_text="Uncertain one text.",
        ),
        PaperCandidate(
            candidate_id=CandidateId("uncertain_two"),
            file_path=RepoRelativePath("library/uncertain-two.pdf"),
            sha256=Sha256Hex("5" * 64),
            metadata=RawPaperMetadata(
                title="Ambiguous Paper",
                authors=("Grace Hopper",),
                year=2026,
            ),
            extracted_text="Uncertain two text.",
        ),
    )

    # When
    result = deduplicate_papers(candidates)

    # Then
    assert len({assignment.paper_id for assignment in result.paper_assignments}) == 2
    assert len(result.merge_candidates) == 1
    assert result.merge_candidates[0].lane is Lane.AMBER
    assert result.merge_candidates[0].requires_audited_decision is True
    assert result.merge_candidates[0].paper_ids == tuple(
        assignment.paper_id for assignment in result.paper_assignments
    )
