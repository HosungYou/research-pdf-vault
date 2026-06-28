from __future__ import annotations

import hashlib
from typing import Final

from research_pdf_vault.fingerprint import (
    normalize_text_for_fingerprint,
    text_fingerprint,
)
from research_pdf_vault.dedup_conflicts import (
    MergeCandidateContext,
    merge_candidates_for,
)
from research_pdf_vault.identity import (
    PaperManifest,
    has_high_priority_conflict,
    identity_keys_for,
    ordered_identity_keys,
    paper_id_from_keys,
    paper_id_from_key,
)
from research_pdf_vault.dedup_models import (
    EMPTY_MANIFEST,
    CandidateEvidence,
    CandidateId,
    DeduplicationResult,
    GroupPaperId,
    MergeCandidate,
    PaperAssignment,
    PaperCandidate,
    PaperInstanceAssignment,
    UnassignedCandidate,
)
from research_pdf_vault.metadata import (
    normalize_metadata,
)
from research_pdf_vault.schema import (
    InstanceId,
    Lane,
    PaperId,
    Sha256Hex,
)

_INSTANCE_ID_DIGEST_LENGTH: Final = 24


def deduplicate_papers(
    candidates: tuple[PaperCandidate, ...],
    manifest: PaperManifest = EMPTY_MANIFEST,
) -> DeduplicationResult:
    evidence = tuple(_candidate_evidence(candidate) for candidate in candidates)
    assigned_evidence = tuple(item for item in evidence if item.identity_keys)
    unassigned_candidates = tuple(
        UnassignedCandidate(
            candidate_id=item.candidate.candidate_id,
            reason="no identifier, citation metadata, or text fingerprint",
        )
        for item in evidence
        if not item.identity_keys
    )
    group_ids = _group_ids_for(assigned_evidence)
    group_paper_ids = _paper_ids_by_group(assigned_evidence, group_ids, manifest)
    assignments = _paper_assignments(assigned_evidence, group_ids, group_paper_ids)
    return DeduplicationResult(
        paper_assignments=assignments,
        paper_instances=tuple(
            _paper_instance(item, assignment.paper_id)
            for item, assignment in zip(assigned_evidence, assignments, strict=True)
        ),
        merge_candidates=merge_candidates_for(
            MergeCandidateContext(
                evidence=assigned_evidence,
                group_ids=group_ids,
                assignments=assignments,
                group_paper_ids=group_paper_ids,
            ),
        ),
        unassigned_candidates=unassigned_candidates,
    )


def _candidate_evidence(candidate: PaperCandidate) -> CandidateEvidence:
    normalized_metadata = normalize_metadata(candidate.metadata)
    fingerprint = _text_fingerprint_or_none(candidate.extracted_text)
    return CandidateEvidence(
        candidate=candidate,
        normalized_metadata=normalized_metadata,
        text_fingerprint=fingerprint,
        identity_keys=frozenset(identity_keys_for(normalized_metadata, fingerprint)),
    )


def _text_fingerprint_or_none(text: str | None) -> Sha256Hex | None:
    if text is None:
        return None
    if normalize_text_for_fingerprint(text) == "":
        return None
    return text_fingerprint(text)


def _group_ids_for(evidence: tuple[CandidateEvidence, ...]) -> tuple[int, ...]:
    parents = list(range(len(evidence)))
    key_owners: dict[PaperIdentityKey, int] = {}
    for index, item in enumerate(evidence):
        for identity_key in item.identity_keys:
            owner = key_owners.get(identity_key)
            if owner is None:
                key_owners[identity_key] = index
            elif _can_share_identity(item, evidence[owner]):
                _union(parents, index, owner)
    return tuple(_find(parents, index) for index in range(len(evidence)))


def _paper_assignments(
    evidence: tuple[CandidateEvidence, ...],
    group_ids: tuple[int, ...],
    group_paper_ids: tuple[GroupPaperId, ...],
) -> tuple[PaperAssignment, ...]:
    paper_ids = {
        group.group_id: group.paper_id
        for group in group_paper_ids
    }
    return tuple(
        PaperAssignment(
            candidate_id=item.candidate.candidate_id,
            paper_id=paper_ids[group_id],
            identity_keys=item.identity_keys,
            normalized_metadata=item.normalized_metadata,
            text_fingerprint=item.text_fingerprint,
        )
        for item, group_id in zip(evidence, group_ids, strict=True)
    )


def _paper_ids_by_group(
    evidence: tuple[CandidateEvidence, ...],
    group_ids: tuple[int, ...],
    manifest: PaperManifest,
) -> tuple[GroupPaperId, ...]:
    group_keys: dict[int, set[PaperIdentityKey]] = {}
    for item, group_id in zip(evidence, group_ids, strict=True):
        group_keys.setdefault(group_id, set()).update(item.identity_keys)
    return tuple(
        GroupPaperId(
            group_id=group_id,
            paper_id=_paper_id_for_keys(
                frozenset(identity_keys),
                manifest,
            ),
            manifest_paper_ids=manifest.paper_ids_for(frozenset(identity_keys)),
        )
        for group_id, identity_keys in group_keys.items()
    )


def _paper_id_for_keys(
    identity_keys: frozenset[PaperIdentityKey],
    manifest: PaperManifest,
) -> PaperId:
    existing = manifest.paper_ids_for(identity_keys)
    if len(existing) == 1:
        return existing[0]
    if len(existing) > 1:
        return paper_id_from_keys(identity_keys)
    ordered_keys = ordered_identity_keys(identity_keys)
    return paper_id_from_key(ordered_keys[0])


def _paper_instance(
    evidence: CandidateEvidence,
    paper_id: PaperId,
) -> PaperInstanceAssignment:
    candidate = evidence.candidate
    return PaperInstanceAssignment(
        instance_id=_instance_id(candidate),
        paper_id=paper_id,
        candidate_id=candidate.candidate_id,
        file_path=candidate.file_path,
        sha256=candidate.sha256,
    )


def _can_share_identity(left: CandidateEvidence, right: CandidateEvidence) -> bool:
    return not has_high_priority_conflict(left.identity_keys, right.identity_keys)


def _instance_id(candidate: PaperCandidate) -> InstanceId:
    if candidate.sha256 is not None:
        return InstanceId(
            f"instance_sha_{candidate.sha256[:_INSTANCE_ID_DIGEST_LENGTH]}",
        )
    digest = hashlib.sha256(candidate.candidate_id.encode("utf-8")).hexdigest()
    return InstanceId(f"instance_candidate_{digest[:_INSTANCE_ID_DIGEST_LENGTH]}")


def _find(parents: list[int], index: int) -> int:
    current = index
    while parents[current] != current:
        current = parents[current]
    return current


def _union(parents: list[int], left: int, right: int) -> None:
    left_root = _find(parents, left)
    right_root = _find(parents, right)
    if left_root != right_root:
        parents[right_root] = left_root
