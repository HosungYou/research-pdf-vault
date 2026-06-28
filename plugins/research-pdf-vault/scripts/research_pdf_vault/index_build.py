from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

from research_pdf_vault.chunking import ChunkBuildRequest, chunks_for_pages
from research_pdf_vault.config import VaultRuntimeConfig
from research_pdf_vault.document_traits import DocumentTraits
from research_pdf_vault.embeddings import EmbeddingBackend, embedding_backend_for
from research_pdf_vault.extraction import DEFAULT_EXTRACTION_POLICY, extract_text
from research_pdf_vault.extraction_types import TextExtractionRequest
from research_pdf_vault.index_status import (
    VECTOR_ARTIFACT_PATH,
    IndexCandidate,
    IndexStatusResult,
    record_quarantine_audit,
    status_result,
    upsert_artifact_status,
)
from research_pdf_vault.scan_db import initialize_scan_database
from research_pdf_vault.schema import (
    InstanceId,
    Lane,
    PaperId,
    StageStatus,
)
from research_pdf_vault.vector_store import (
    clear_index_for_paper,
    initialize_index_tables,
    store_chunks,
)


@dataclass(frozen=True, slots=True)
class IndexBuildSummary:
    indexed_count: int
    chunk_count: int
    vector_count: int
    quarantined_count: int
    skipped_count: int


@dataclass(frozen=True, slots=True)
class IndexCounters:
    indexed: int = 0
    chunks: int = 0
    vectors: int = 0
    quarantined: int = 0
    skipped: int = 0


@dataclass(frozen=True, slots=True)
class IndexRunState:
    connection: sqlite3.Connection
    config: VaultRuntimeConfig
    backend: EmbeddingBackend


def build_local_index(config: VaultRuntimeConfig) -> IndexBuildSummary:
    backend = embedding_backend_for(config.embedding_backend)
    config.manifest_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.manifest_db) as connection:
        initialize_scan_database(connection)
        initialize_index_tables(connection)
        state = IndexRunState(connection=connection, config=config, backend=backend)
        counters = IndexCounters()
        for candidate in _index_candidates(connection):
            counters = _process_candidate(state, candidate, counters)
    return IndexBuildSummary(
        indexed_count=counters.indexed,
        chunk_count=counters.chunks,
        vector_count=counters.vectors,
        quarantined_count=counters.quarantined,
        skipped_count=counters.skipped,
    )


def _index_candidates(connection: sqlite3.Connection) -> tuple[IndexCandidate, ...]:
    rows = connection.execute(
        "SELECT p.paper_id, p.lane, p.normalized_identifiers, i.instance_id, i.file_path "
        "FROM paper AS p JOIN paper_instance AS i ON i.paper_id = p.paper_id "
        "WHERE i.instance_status = 'available' ORDER BY p.paper_id, i.instance_id",
    )
    return tuple(
        IndexCandidate(
            paper_id=PaperId(str(row[0])),
            lane=Lane(str(row[1])),
            normalized_identifiers=str(row[2]),
            instance_id=InstanceId(str(row[3])),
            file_path=str(row[4]),
        )
        for row in rows
    )


def _process_candidate(
    state: IndexRunState,
    candidate: IndexCandidate,
    counters: IndexCounters,
) -> IndexCounters:
    match candidate.lane:
        case Lane.RED:
            _quarantine_candidate(state, candidate)
            return IndexCounters(
                indexed=counters.indexed,
                chunks=counters.chunks,
                vectors=counters.vectors,
                quarantined=counters.quarantined + 1,
                skipped=counters.skipped,
            )
        case Lane.AMBER:
            _skip_candidate(state, candidate, "amber lane awaits review")
            return _skipped_counters(counters)
        case Lane.GREEN:
            return _index_green_candidate(state, candidate, counters)
        case unreachable:
            assert_never(unreachable)


def _index_green_candidate(
    state: IndexRunState,
    candidate: IndexCandidate,
    counters: IndexCounters,
) -> IndexCounters:
    if _metadata_is_gap_only(candidate.normalized_identifiers):
        _skip_candidate(state, candidate, "gap only metadata row")
        return _skipped_counters(counters)
    source_path = _source_path_for(state.config.storage_roots, candidate.file_path)
    if source_path is None:
        _skip_candidate(state, candidate, "source file unavailable")
        return _skipped_counters(counters)
    result = extract_text(
        TextExtractionRequest(
            source_path=source_path,
            paper_id=candidate.paper_id,
            instance_id=candidate.instance_id,
            lane=candidate.lane,
            traits=DocumentTraits(),
            artifact_dir=state.config.cache_root / "text",
        ),
        policy=DEFAULT_EXTRACTION_POLICY,
    )
    chunks = chunks_for_pages(
        ChunkBuildRequest(
            paper_id=candidate.paper_id,
            instance_id=candidate.instance_id,
            pages=result.pages,
        ),
    )
    if not chunks:
        _skip_candidate(state, candidate, "no indexable extracted text")
        return _skipped_counters(counters)
    digest = store_chunks(state.connection, chunks, state.backend)
    upsert_artifact_status(
        state.connection,
        candidate,
        IndexStatusResult(
            stage_status=StageStatus.COMPLETE,
            artifact_digest=digest,
            vector_artifact_path=VECTOR_ARTIFACT_PATH,
        ),
    )
    return IndexCounters(
        indexed=counters.indexed + 1,
        chunks=counters.chunks + len(chunks),
        vectors=counters.vectors + len(chunks),
        quarantined=counters.quarantined,
        skipped=counters.skipped,
    )


def _quarantine_candidate(
    state: IndexRunState,
    candidate: IndexCandidate,
) -> None:
    clear_index_for_paper(state.connection, candidate.paper_id)
    upsert_artifact_status(
        state.connection,
        candidate,
        status_result(StageStatus.QUARANTINED, candidate, "red lane cannot be indexed"),
    )
    record_quarantine_audit(state.connection, candidate)


def _skip_candidate(
    state: IndexRunState,
    candidate: IndexCandidate,
    reason: str,
) -> None:
    clear_index_for_paper(state.connection, candidate.paper_id)
    upsert_artifact_status(
        state.connection,
        candidate,
        status_result(StageStatus.FAILED, candidate, reason),
    )


def _source_path_for(roots: tuple[Path, ...], relative_path: str) -> Path | None:
    path_parts = Path(relative_path).parts
    for root in roots:
        if path_parts and path_parts[0] == root.name:
            return root.joinpath(*path_parts[1:])
    return None


def _metadata_is_gap_only(normalized_identifiers: str) -> bool:
    compact = "".join(normalized_identifiers.casefold().split())
    return '"support_tag":"gap"' in compact or '"gap_only":true' in compact


def _skipped_counters(counters: IndexCounters) -> IndexCounters:
    return IndexCounters(
        indexed=counters.indexed,
        chunks=counters.chunks,
        vectors=counters.vectors,
        quarantined=counters.quarantined,
        skipped=counters.skipped + 1,
    )
