from __future__ import annotations

from dataclasses import dataclass

from research_pdf_vault.dedup_models import (
    CandidateEvidence,
    GroupPaperId,
    MergeCandidate,
    PaperAssignment,
)
from research_pdf_vault.identity import (
    has_high_priority_conflict,
    has_shared_lower_priority_key,
)
from research_pdf_vault.schema import Lane, PaperId


@dataclass(frozen=True, slots=True)
class MergeCandidateContext:
    evidence: tuple[CandidateEvidence, ...]
    group_ids: tuple[int, ...]
    assignments: tuple[PaperAssignment, ...]
    group_paper_ids: tuple[GroupPaperId, ...]


@dataclass(frozen=True, slots=True)
class PairMergeContext:
    left: CandidateEvidence
    right: CandidateEvidence
    paper_ids: tuple[PaperId, PaperId]
    reason: str


def merge_candidates_for(context: MergeCandidateContext) -> tuple[MergeCandidate, ...]:
    candidates = list(_manifest_merge_candidates(context))
    for left_index, left in enumerate(context.evidence):
        for right_index in range(left_index + 1, len(context.evidence)):
            right = context.evidence[right_index]
            if context.group_ids[left_index] == context.group_ids[right_index]:
                continue
            if _blocked_high_priority_merge(left, right):
                candidates.append(
                    _pair_merge_candidate(
                        PairMergeContext(
                            left=left,
                            right=right,
                            paper_ids=(
                                context.assignments[left_index].paper_id,
                                context.assignments[right_index].paper_id,
                            ),
                            reason=(
                                "shared lower-priority identity conflicts "
                                "with DOI/ISBN/arXiv"
                            ),
                        ),
                    ),
                )
            elif _same_title_year(left, right) and _authors_conflict(left, right):
                candidates.append(
                    _pair_merge_candidate(
                        PairMergeContext(
                            left=left,
                            right=right,
                            paper_ids=(
                                context.assignments[left_index].paper_id,
                                context.assignments[right_index].paper_id,
                            ),
                            reason="same normalized title/year with conflicting authors",
                        ),
                    ),
                )
    return tuple(candidates)


def _blocked_high_priority_merge(
    left: CandidateEvidence,
    right: CandidateEvidence,
) -> bool:
    return has_high_priority_conflict(
        left.identity_keys,
        right.identity_keys,
    ) and has_shared_lower_priority_key(left.identity_keys, right.identity_keys)


def _pair_merge_candidate(context: PairMergeContext) -> MergeCandidate:
    return MergeCandidate(
        candidate_ids=(
            context.left.candidate.candidate_id,
            context.right.candidate.candidate_id,
        ),
        paper_ids=context.paper_ids,
        lane=Lane.AMBER,
        reason=f"{context.reason}; audited merge decision required",
        requires_audited_decision=True,
    )


def _manifest_merge_candidates(
    context: MergeCandidateContext,
) -> tuple[MergeCandidate, ...]:
    return tuple(
        MergeCandidate(
            candidate_ids=tuple(
                item.candidate.candidate_id
                for item, group_id in zip(
                    context.evidence,
                    context.group_ids,
                    strict=True,
                )
                if group_id == group.group_id
            ),
            paper_ids=(*group.manifest_paper_ids, group.paper_id),
            lane=Lane.AMBER,
            reason=(
                "identity keys match multiple stored paper IDs; "
                "audited merge decision required"
            ),
            requires_audited_decision=True,
        )
        for group in context.group_paper_ids
        if len(group.manifest_paper_ids) > 1
    )


def _same_title_year(left: CandidateEvidence, right: CandidateEvidence) -> bool:
    left_metadata = left.normalized_metadata
    right_metadata = right.normalized_metadata
    return (
        left_metadata.title is not None
        and left_metadata.title == right_metadata.title
        and left_metadata.year is not None
        and left_metadata.year == right_metadata.year
    )


def _authors_conflict(left: CandidateEvidence, right: CandidateEvidence) -> bool:
    left_authors = left.normalized_metadata.authors
    right_authors = right.normalized_metadata.authors
    return bool(left_authors and right_authors and left_authors != right_authors)
