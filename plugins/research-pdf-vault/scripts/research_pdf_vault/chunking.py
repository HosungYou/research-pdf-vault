from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final, NewType

from research_pdf_vault.extraction_types import ExtractedTextPage
from research_pdf_vault.schema import InstanceId, PaperId, SourceLocation

ChunkId = NewType("ChunkId", str)
ContentDigest = NewType("ContentDigest", str)
CHUNK_CHAR_LIMIT: Final = 700
_CHUNK_ID_LENGTH: Final = 24


@dataclass(frozen=True, slots=True)
class ChunkBuildRequest:
    paper_id: PaperId
    instance_id: InstanceId
    pages: tuple[ExtractedTextPage, ...]


@dataclass(frozen=True, slots=True)
class TextChunk:
    chunk_id: ChunkId
    paper_id: PaperId
    instance_id: InstanceId
    source_location: SourceLocation
    text: str
    content_digest: ContentDigest


@dataclass(frozen=True, slots=True)
class PageChunkRequest:
    paper_id: PaperId
    instance_id: InstanceId
    page: ExtractedTextPage


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    paper_id: PaperId
    instance_id: InstanceId
    source_location: SourceLocation
    text: str


def chunks_for_pages(request: ChunkBuildRequest) -> tuple[TextChunk, ...]:
    chunks: list[TextChunk] = []
    for page in request.pages:
        chunks.extend(
            _chunks_for_page(
                PageChunkRequest(
                    paper_id=request.paper_id,
                    instance_id=request.instance_id,
                    page=page,
                ),
            ),
        )
    return tuple(chunks)


def _chunks_for_page(request: PageChunkRequest) -> tuple[TextChunk, ...]:
    page_text = request.page.text.strip()
    if page_text == "":
        return ()
    chunks: list[TextChunk] = []
    start = 0
    while start < len(page_text):
        end = min(start + CHUNK_CHAR_LIMIT, len(page_text))
        text = page_text[start:end].strip()
        if text:
            location = SourceLocation(
                page=request.page.source_location.page,
                start_offset=request.page.source_location.start_offset + start,
                end_offset=request.page.source_location.start_offset + start + len(text),
            )
            chunks.append(
                _chunk_from_draft(
                    ChunkDraft(
                        paper_id=request.paper_id,
                        instance_id=request.instance_id,
                        source_location=location,
                        text=text,
                    ),
                ),
            )
        start = end
    return tuple(chunks)


def _chunk_from_draft(draft: ChunkDraft) -> TextChunk:
    digest = _digest_text(
        "\n".join(
            (
                draft.paper_id,
                draft.instance_id,
                str(draft.source_location.page),
                str(draft.source_location.start_offset),
                str(draft.source_location.end_offset),
                draft.text,
            ),
        ),
    )
    return TextChunk(
        chunk_id=ChunkId(f"chunk_{digest[:_CHUNK_ID_LENGTH]}"),
        paper_id=draft.paper_id,
        instance_id=draft.instance_id,
        source_location=draft.source_location,
        text=draft.text,
        content_digest=ContentDigest(f"sha256:{digest}"),
    )


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
