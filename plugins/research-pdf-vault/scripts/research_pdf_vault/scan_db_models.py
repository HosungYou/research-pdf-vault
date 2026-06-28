from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from research_pdf_vault.sync_ready import SyncReadyResult


@dataclass(frozen=True, slots=True)
class ScannedFile:
    source_path: Path
    relative_path: str
    result: SyncReadyResult


@dataclass(frozen=True, slots=True)
class ScanBatch:
    observed_at: str
    observed_paths: frozenset[str]


@dataclass(frozen=True, slots=True)
class ReadyFileIdentity:
    relative_path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class PaperRecord:
    paper_id: str
    title: str
    observed_at: str


@dataclass(frozen=True, slots=True)
class InstanceRecord:
    instance_id: str
    paper_id: str
    item: ScannedFile
    status: str
    observed_at: str


@dataclass(frozen=True, slots=True)
class ScanDataError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message
