from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum, unique
from typing import Final

from research_pdf_vault.metadata import NormalizedPaperMetadata
from research_pdf_vault.schema import PaperId, Sha256Hex


@unique
class IdentityKind(StrEnum):
    DOI = "doi"
    ISBN = "isbn"
    ARXIV = "arxiv"
    CITATION = "citation"
    TEXT_FINGERPRINT = "text"


@dataclass(frozen=True, slots=True)
class PaperIdentityKey:
    kind: IdentityKind
    value: str


@dataclass(frozen=True, slots=True)
class ManifestPaper:
    paper_id: PaperId
    identity_keys: frozenset[PaperIdentityKey]


@dataclass(frozen=True, slots=True)
class PaperManifest:
    papers: tuple[ManifestPaper, ...] = ()

    def paper_ids_for(
        self,
        identity_keys: frozenset[PaperIdentityKey],
    ) -> tuple[PaperId, ...]:
        found: set[PaperId] = set()
        for paper in self.papers:
            if paper.identity_keys & identity_keys:
                found.add(paper.paper_id)
        return tuple(sorted(found))


_IDENTITY_PRIORITY: Final = {
    IdentityKind.DOI: 0,
    IdentityKind.ISBN: 1,
    IdentityKind.ARXIV: 2,
    IdentityKind.CITATION: 3,
    IdentityKind.TEXT_FINGERPRINT: 4,
}
_PAPER_ID_DIGEST_LENGTH: Final = 24
_HIGH_PRIORITY_KINDS: Final = frozenset(
    (IdentityKind.DOI, IdentityKind.ISBN, IdentityKind.ARXIV),
)
_LOWER_PRIORITY_KINDS: Final = frozenset(
    (IdentityKind.CITATION, IdentityKind.TEXT_FINGERPRINT),
)


def identity_keys_for(
    metadata: NormalizedPaperMetadata,
    fingerprint: Sha256Hex | None,
) -> tuple[PaperIdentityKey, ...]:
    keys: list[PaperIdentityKey] = []
    if metadata.doi is not None:
        keys.append(PaperIdentityKey(kind=IdentityKind.DOI, value=metadata.doi))
    if metadata.isbn is not None:
        keys.append(PaperIdentityKey(kind=IdentityKind.ISBN, value=metadata.isbn))
    if metadata.arxiv_id is not None:
        keys.append(PaperIdentityKey(kind=IdentityKind.ARXIV, value=metadata.arxiv_id))
    citation_value = citation_identity_value(metadata)
    if citation_value is not None:
        keys.append(PaperIdentityKey(kind=IdentityKind.CITATION, value=citation_value))
    if fingerprint is not None:
        keys.append(PaperIdentityKey(kind=IdentityKind.TEXT_FINGERPRINT, value=fingerprint))
    return tuple(keys)


def citation_identity_value(metadata: NormalizedPaperMetadata) -> str | None:
    if metadata.title is None or metadata.year is None or not metadata.authors:
        return None
    joined = "\n".join((metadata.title, str(metadata.year), "\n".join(metadata.authors)))
    return _digest_text(joined)


def ordered_identity_keys(
    identity_keys: frozenset[PaperIdentityKey],
) -> tuple[PaperIdentityKey, ...]:
    return tuple(sorted(identity_keys, key=_identity_key_rank))


def paper_id_from_key(identity_key: PaperIdentityKey) -> PaperId:
    digest = _digest_text(f"{identity_key.kind.value}:{identity_key.value}")
    return PaperId(f"paper_{identity_key.kind.value}_{digest}")


def paper_id_from_keys(identity_keys: frozenset[PaperIdentityKey]) -> PaperId:
    joined = "\n".join(
        f"{identity_key.kind.value}:{identity_key.value}"
        for identity_key in ordered_identity_keys(identity_keys)
    )
    return PaperId(f"paper_review_{_digest_text(joined)}")


def has_high_priority_conflict(
    left: frozenset[PaperIdentityKey],
    right: frozenset[PaperIdentityKey],
) -> bool:
    for kind in _HIGH_PRIORITY_KINDS:
        left_values = {key.value for key in left if key.kind is kind}
        right_values = {key.value for key in right if key.kind is kind}
        if left_values and right_values and left_values.isdisjoint(right_values):
            return True
    return False


def has_shared_lower_priority_key(
    left: frozenset[PaperIdentityKey],
    right: frozenset[PaperIdentityKey],
) -> bool:
    return any(
        key.kind in _LOWER_PRIORITY_KINDS
        for key in left & right
    )


def _identity_key_rank(identity_key: PaperIdentityKey) -> tuple[int, str]:
    return (_IDENTITY_PRIORITY[identity_key.kind], identity_key.value)


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:_PAPER_ID_DIGEST_LENGTH]
