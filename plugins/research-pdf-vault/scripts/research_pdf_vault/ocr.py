from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique
from pathlib import Path
from typing import Protocol


@unique
class OcrStatus(StrEnum):
    NOT_NEEDED = "not_needed"
    SKIPPED = "skipped"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class OcrPageRequest:
    source_path: Path
    page: int
    constrained: bool
    max_chars: int


class OcrAdapter(Protocol):
    def extract_page_text(self, request: OcrPageRequest) -> str:
        ...
