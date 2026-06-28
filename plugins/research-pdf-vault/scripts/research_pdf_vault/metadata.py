from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Final

_DOI_PREFIX_RE: Final = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.I)
_ARXIV_PREFIX_RE: Final = re.compile(r"^(?:https?://arxiv\.org/abs/|arxiv:)", re.I)
_ARXIV_VERSION_RE: Final = re.compile(r"v[0-9]+$", re.I)
_ISBN_PREFIX_RE: Final = re.compile(r"^isbn(?:-1[03])?:", re.I)
_WORD_RE: Final = re.compile(r"[a-z0-9]+")
_ISBN_CHAR_RE: Final = re.compile(r"[0-9xX]")


@dataclass(frozen=True, slots=True)
class RawPaperMetadata:
    doi: str | None = None
    isbn: str | None = None
    arxiv_id: str | None = None
    title: str | None = None
    authors: tuple[str, ...] = ()
    year: int | None = None


@dataclass(frozen=True, slots=True)
class NormalizedPaperMetadata:
    doi: str | None
    isbn: str | None
    arxiv_id: str | None
    title: str | None
    authors: tuple[str, ...]
    year: int | None


def normalize_metadata(metadata: RawPaperMetadata) -> NormalizedPaperMetadata:
    return NormalizedPaperMetadata(
        doi=_normalize_doi(metadata.doi),
        isbn=_normalize_isbn(metadata.isbn),
        arxiv_id=_normalize_arxiv_id(metadata.arxiv_id),
        title=_normalize_words(metadata.title),
        authors=tuple(
            normalized
            for author in metadata.authors
            if (normalized := _normalize_words(author)) is not None
        ),
        year=metadata.year,
    )


def _clean_text(raw: str | None) -> str | None:
    if raw is None:
        return None
    cleaned = raw.strip()
    if cleaned == "":
        return None
    return unicodedata.normalize("NFKC", cleaned)


def _normalize_doi(raw: str | None) -> str | None:
    cleaned = _clean_text(raw)
    if cleaned is None:
        return None
    without_prefix = _DOI_PREFIX_RE.sub("", cleaned).strip()
    canonical = without_prefix.rstrip(".,;").casefold()
    if canonical == "":
        return None
    return canonical


def _normalize_isbn(raw: str | None) -> str | None:
    cleaned = _clean_text(raw)
    if cleaned is None:
        return None
    without_prefix = _ISBN_PREFIX_RE.sub("", cleaned).strip()
    canonical = "".join(_ISBN_CHAR_RE.findall(without_prefix)).upper()
    if canonical == "":
        return None
    return canonical


def _normalize_arxiv_id(raw: str | None) -> str | None:
    cleaned = _clean_text(raw)
    if cleaned is None:
        return None
    without_prefix = _ARXIV_PREFIX_RE.sub("", cleaned).strip()
    canonical = _ARXIV_VERSION_RE.sub("", without_prefix.rstrip(".,;")).casefold()
    if canonical == "":
        return None
    return canonical


def _normalize_words(raw: str | None) -> str | None:
    cleaned = _clean_text(raw)
    if cleaned is None:
        return None
    words = _WORD_RE.findall(cleaned.casefold())
    if not words:
        return None
    return " ".join(words)
