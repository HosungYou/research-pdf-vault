from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from research_pdf_vault.chunking import TextChunk
from research_pdf_vault.schema import PaperId


@dataclass(frozen=True, slots=True)
class FtsUnavailableError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def initialize_fts(connection: sqlite3.Connection) -> None:
    try:
        connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts "
            "USING fts5(chunk_id UNINDEXED, paper_id UNINDEXED, text)",
        )
    except sqlite3.OperationalError as error:
        raise FtsUnavailableError("SQLite FTS5 is required for chunk_fts") from error


def clear_fts_for_paper(connection: sqlite3.Connection, paper_id: PaperId) -> None:
    connection.execute("DELETE FROM chunk_fts WHERE paper_id = ?", (paper_id,))


def replace_fts_chunks(
    connection: sqlite3.Connection,
    chunks: tuple[TextChunk, ...],
) -> None:
    for chunk in chunks:
        connection.execute("DELETE FROM chunk_fts WHERE chunk_id = ?", (chunk.chunk_id,))
        connection.execute(
            "INSERT INTO chunk_fts (chunk_id, paper_id, text) VALUES (?, ?, ?)",
            (chunk.chunk_id, chunk.paper_id, chunk.text),
        )
