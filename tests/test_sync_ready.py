from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

PDF_BYTES: Final = (
    b"%PDF-1.4\n"
    b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
    b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
    b"3 0 obj << /Type /Page /Parent 2 0 R >> endobj\n"
    b"%%EOF\n"
)


@dataclass(frozen=True, slots=True)
class FakeSample:
    size_bytes: int
    mtime_ns: int


class ChangingSampler:
    __slots__ = ("call_count", "first", "second")

    def __init__(self, first: FakeSample, second: FakeSample) -> None:
        self.first = first
        self.second = second
        self.call_count = 0

    def sample(self, path: Path) -> FakeSample:
        _ = path
        self.call_count += 1
        if self.call_count == 1:
            return self.first
        return self.second


def test_probe_sync_ready_when_pdf_is_readable_then_returns_ready_with_sha(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.sync_ready import SyncReadyStatus, probe_sync_ready

    # Given
    pdf_path = tmp_path / "unit-ready.pdf"
    pdf_path.write_bytes(PDF_BYTES)

    # When
    result = probe_sync_ready(pdf_path)

    # Then
    assert result.status is SyncReadyStatus.READY
    assert result.sha256 == hashlib.sha256(PDF_BYTES).hexdigest()
    assert result.retry_after_seconds is None


def test_probe_sync_ready_when_file_changes_between_samples_then_pending(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.sync_ready import SyncReadyStatus, probe_sync_ready

    # Given
    pdf_path = tmp_path / "unit-changing.pdf"
    pdf_path.write_bytes(PDF_BYTES)
    first = FakeSample(size_bytes=len(PDF_BYTES), mtime_ns=10)
    second = FakeSample(size_bytes=len(PDF_BYTES), mtime_ns=11)

    # When
    result = probe_sync_ready(
        pdf_path,
        sampler=ChangingSampler(first=first, second=second),
    )

    # Then
    assert result.status is SyncReadyStatus.UNSTABLE_FILE
    assert result.sha256 is None
    assert result.retry_after_seconds == 300


def test_probe_sync_ready_when_header_is_invalid_then_pending_with_hash(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.sync_ready import SyncReadyStatus, probe_sync_ready

    # Given
    invalid_bytes = b"not a pdf\n%%EOF\n"
    pdf_path = tmp_path / "unit-invalid-header.pdf"
    pdf_path.write_bytes(invalid_bytes)

    # When
    result = probe_sync_ready(pdf_path)

    # Then
    assert result.status is SyncReadyStatus.INVALID_PDF_HEADER
    assert result.sha256 == hashlib.sha256(invalid_bytes).hexdigest()
    assert result.retry_after_seconds == 300


def test_probe_sync_ready_when_probe_read_times_out_then_pending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import research_pdf_vault.sync_ready as sync_ready

    # Given
    pdf_path = tmp_path / "unit-timeout.pdf"
    pdf_path.write_bytes(PDF_BYTES)

    def raise_timeout(path: Path, timeout_seconds: float) -> None:
        _ = path
        _ = timeout_seconds
        raise sync_ready.SyncProbeTimeoutError

    monkeypatch.setattr(sync_ready, "_read_probe_byte", raise_timeout)

    # When
    result = sync_ready.probe_sync_ready(pdf_path)

    # Then
    assert result.status is sync_ready.SyncReadyStatus.READ_ERROR
    assert result.provider_status == "read_timeout"
    assert result.retry_after_seconds == 300
