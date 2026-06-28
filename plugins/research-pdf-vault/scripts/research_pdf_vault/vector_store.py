from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from typing import Final

from research_pdf_vault.chunking import TextChunk
from research_pdf_vault.embeddings import EmbeddingBackend
from research_pdf_vault.fts import clear_fts_for_paper, initialize_fts, replace_fts_chunks
from research_pdf_vault.schema import ArtifactDigest, PaperId

INDEX_SQL: Final = "\n".join(
    (
        "CREATE TABLE IF NOT EXISTS index_chunk (chunk_id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES paper(paper_id), instance_id TEXT NOT NULL REFERENCES paper_instance(instance_id), source_page INTEGER NOT NULL CHECK (source_page >= 1), start_offset INTEGER NOT NULL CHECK (start_offset >= 0), end_offset INTEGER NOT NULL CHECK (end_offset > start_offset), text TEXT NOT NULL CHECK (length(text) > 0), content_digest TEXT NOT NULL CHECK (content_digest GLOB 'sha256:*' AND length(content_digest) = 71));",
        "CREATE TABLE IF NOT EXISTS chunk_embedding (chunk_id TEXT PRIMARY KEY REFERENCES index_chunk(chunk_id), paper_id TEXT NOT NULL REFERENCES paper(paper_id), embedding_backend TEXT NOT NULL, vector_json TEXT NOT NULL CHECK (length(vector_json) > 2), vector_digest TEXT NOT NULL CHECK (vector_digest GLOB 'sha256:*' AND length(vector_digest) = 71));",
    ),
)


@dataclass(frozen=True, slots=True)
class StoredVector:
    chunk: TextChunk
    embedding_backend: str
    vector_json: str
    vector_digest: str


def initialize_index_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(INDEX_SQL)
    initialize_fts(connection)


def clear_index_for_paper(connection: sqlite3.Connection, paper_id: PaperId) -> None:
    clear_fts_for_paper(connection, paper_id)
    connection.execute("DELETE FROM chunk_embedding WHERE paper_id = ?", (paper_id,))
    connection.execute("DELETE FROM index_chunk WHERE paper_id = ?", (paper_id,))
    connection.execute("DELETE FROM extracted_passage WHERE paper_id = ?", (paper_id,))


def store_chunks(
    connection: sqlite3.Connection,
    chunks: tuple[TextChunk, ...],
    backend: EmbeddingBackend,
) -> ArtifactDigest:
    if chunks:
        clear_index_for_paper(connection, chunks[0].paper_id)
    vectors = tuple(_stored_vector(chunk, backend) for chunk in chunks)
    for chunk in chunks:
        _insert_chunk(connection, chunk)
        _insert_extracted_passage(connection, chunk)
    for vector in vectors:
        _insert_vector(connection, vector)
    replace_fts_chunks(connection, chunks)
    return _artifact_digest(vectors)


def _insert_chunk(connection: sqlite3.Connection, chunk: TextChunk) -> None:
    connection.execute(
        "INSERT INTO index_chunk (chunk_id, paper_id, instance_id, source_page, start_offset, end_offset, text, content_digest) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            chunk.chunk_id,
            chunk.paper_id,
            chunk.instance_id,
            chunk.source_location.page,
            chunk.source_location.start_offset,
            chunk.source_location.end_offset,
            chunk.text,
            chunk.content_digest,
        ),
    )


def _insert_extracted_passage(connection: sqlite3.Connection, chunk: TextChunk) -> None:
    passage_id = f"passage_{chunk.chunk_id.removeprefix('chunk_')}"
    connection.execute(
        "INSERT INTO extracted_passage (schema_version, passage_id, paper_id, instance_id, source_page, start_offset, end_offset, text, support_tag) "
        "VALUES ('1.0.0', ?, ?, ?, ?, ?, ?, ?, 'context')",
        (
            passage_id,
            chunk.paper_id,
            chunk.instance_id,
            chunk.source_location.page,
            chunk.source_location.start_offset,
            chunk.source_location.end_offset,
            chunk.text,
        ),
    )


def _insert_vector(connection: sqlite3.Connection, vector: StoredVector) -> None:
    connection.execute(
        "INSERT INTO chunk_embedding (chunk_id, paper_id, embedding_backend, vector_json, vector_digest) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            vector.chunk.chunk_id,
            vector.chunk.paper_id,
            vector.embedding_backend,
            vector.vector_json,
            vector.vector_digest,
        ),
    )


def _stored_vector(chunk: TextChunk, backend: EmbeddingBackend) -> StoredVector:
    vector_json = json.dumps(list(backend.embed(chunk.text)), separators=(",", ":"))
    return StoredVector(
        chunk=chunk,
        embedding_backend=backend.name,
        vector_json=vector_json,
        vector_digest=f"sha256:{_digest_text(vector_json)}",
    )


def _artifact_digest(vectors: tuple[StoredVector, ...]) -> ArtifactDigest:
    payload = "\n".join(
        f"{vector.chunk.content_digest}:{vector.vector_digest}" for vector in vectors
    )
    return ArtifactDigest(f"sha256:{_digest_text(payload)}")


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
