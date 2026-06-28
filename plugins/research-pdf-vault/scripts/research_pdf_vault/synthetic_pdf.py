from __future__ import annotations

from typing import Final

from research_pdf_vault.extraction_types import ExtractedTextPage
from research_pdf_vault.schema import SourceLocation

TEXT_PAGE_PREFIX: Final = "%%RPV_PAGE"
SCANNED_PAGE_PREFIX: Final = "%%RPV_SCANNED_PAGE"
PAGE_END_MARKER: Final = "%%RPV_END_PAGE"


def pdf_block_reason(data: bytes) -> str | None:
    if not data.startswith(b"%PDF"):
        return "corrupt_pdf_blocked"
    if b"%%EOF" not in data:
        return "corrupt_pdf_blocked"
    if b"/Encrypt" in data:
        return "encrypted_pdf_blocked"
    return None


def synthetic_text_pages(data: bytes) -> tuple[ExtractedTextPage, ...]:
    pages: list[ExtractedTextPage] = []
    page_number: int | None = None
    lines: list[str] = []
    for line in _decoded_lines(data):
        if line.startswith(TEXT_PAGE_PREFIX):
            page_number = _page_number(line, TEXT_PAGE_PREFIX)
            lines = []
        elif line == PAGE_END_MARKER and page_number is not None:
            page_text = "\n".join(lines).strip()
            if page_text:
                pages.append(page_from_text(page_number, page_text))
            page_number = None
            lines = []
        elif page_number is not None:
            lines.append(line)
    return tuple(pages)


def synthetic_scanned_pages(data: bytes) -> tuple[int, ...]:
    pages: list[int] = []
    for line in _decoded_lines(data):
        if line.startswith(SCANNED_PAGE_PREFIX):
            pages.append(_page_number(line, SCANNED_PAGE_PREFIX))
    if pages:
        return tuple(pages)
    return (1,)


def page_from_text(page_number: int, text: str) -> ExtractedTextPage:
    return ExtractedTextPage(
        source_location=SourceLocation(
            page=page_number,
            start_offset=0,
            end_offset=len(text),
        ),
        text=text,
    )


def _decoded_lines(data: bytes) -> tuple[str, ...]:
    return tuple(data.decode("utf-8", errors="replace").splitlines())


def _page_number(line: str, prefix: str) -> int:
    raw_page = line.removeprefix(prefix).strip()
    if raw_page.isdecimal():
        return int(raw_page)
    return 1
