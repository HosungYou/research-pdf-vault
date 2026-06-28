from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from research_pdf_vault.identity import PaperIdentityKey, PaperManifest
from research_pdf_vault.metadata import NormalizedPaperMetadata, RawPaperMetadata
from research_pdf_vault.schema import InstanceId, Lane, PaperId, RepoRelativePath, Sha256Hex

CandidateId = NewType("CandidateId", str)
EMPTY_MANIFEST = PaperManifest()


@dataclass(frozen=True, slots=True)
class PaperCandidate:
    candidate_id: CandidateId
    file_path: RepoRelativePath
    sha256: Sha256Hex | None
    metadata: RawPaperMetadata
    extracted_text: str | None


@dataclass(frozen=True, slots=True)
class PaperAssignment:
    candidate_id: CandidateId
    paper_id: PaperId
    identity_keys: frozenset[PaperIdentityKey]
    normalized_metadata: NormalizedPaperMetadata
    text_fingerprint: Sha256Hex | None


@dataclass(frozen=True, slots=True)
class PaperInstanceAssignment:
    instance_id: InstanceId
    paper_id: PaperId
    candidate_id: CandidateId
    file_path: RepoRelativePath
    sha256: Sha256Hex | None


@dataclass(frozen=True, slots=True)
class MergeCandidate:
    candidate_ids: tuple[CandidateId, ...]
    paper_ids: tuple[PaperId, ...]
    lane: Lane
    reason: str
    requires_audited_decision: bool


@dataclass(frozen=True, slots=True)
class UnassignedCandidate:
    candidate_id: CandidateId
    reason: str


@dataclass(frozen=True, slots=True)
class DeduplicationResult:
    paper_assignments: tuple[PaperAssignment, ...]
    paper_instances: tuple[PaperInstanceAssignment, ...]
    merge_candidates: tuple[MergeCandidate, ...]
    unassigned_candidates: tuple[UnassignedCandidate, ...]


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    candidate: PaperCandidate
    normalized_metadata: NormalizedPaperMetadata
    text_fingerprint: Sha256Hex | None
    identity_keys: frozenset[PaperIdentityKey]


@dataclass(frozen=True, slots=True)
class GroupPaperId:
    group_id: int
    paper_id: PaperId
    manifest_paper_ids: tuple[PaperId, ...] = ()
