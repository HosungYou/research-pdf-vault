from __future__ import annotations

import hashlib
import signal
from dataclasses import dataclass
from enum import StrEnum, unique
from pathlib import Path
from types import FrameType
from typing import Final, Protocol, assert_never

RETRY_AFTER_SECONDS: Final = 300
READ_PROBE_TIMEOUT_SECONDS: Final = 0.5


class Sample(Protocol):
    size_bytes: int
    mtime_ns: int


class Sampler(Protocol):
    def sample(self, path: Path) -> Sample: ...


@unique
class SyncReadyStatus(StrEnum):
    READY = "ready"
    DRY_RUN_METADATA_ONLY = "dry_run_metadata_only"
    MISSING_PATH = "missing_path"
    NOT_REGULAR_FILE = "not_regular_file"
    READ_ERROR = "read_error"
    UNSTABLE_FILE = "unstable_file"
    INVALID_PDF_HEADER = "invalid_pdf_header"
    INVALID_PDF_PARSE = "invalid_pdf_parse"


@dataclass(frozen=True, slots=True)
class FileSample:
    size_bytes: int
    mtime_ns: int


class SyncProbeTimeoutError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PathSampler:
    def sample(self, path: Path) -> FileSample:
        stat = path.stat()
        return FileSample(size_bytes=stat.st_size, mtime_ns=stat.st_mtime_ns)


@dataclass(frozen=True, slots=True)
class SyncReadyResult:
    status: SyncReadyStatus
    sha256: str | None
    size_bytes: int | None
    mtime_ns: int | None
    retry_after_seconds: int | None
    provider_status: str | None = None

    @property
    def ready(self) -> bool:
        match self.status:
            case SyncReadyStatus.READY:
                return True
            case (
                SyncReadyStatus.DRY_RUN_METADATA_ONLY
                | SyncReadyStatus.MISSING_PATH
                | SyncReadyStatus.NOT_REGULAR_FILE
                | SyncReadyStatus.READ_ERROR
                | SyncReadyStatus.UNSTABLE_FILE
                | SyncReadyStatus.INVALID_PDF_HEADER
                | SyncReadyStatus.INVALID_PDF_PARSE
            ):
                return False
            case unreachable:
                assert_never(unreachable)


def probe_sync_metadata(path: Path, provider: str) -> SyncReadyResult:
    if not path.exists():
        return _pending(SyncReadyStatus.MISSING_PATH, provider_status=provider)
    if not path.is_file():
        return _pending(SyncReadyStatus.NOT_REGULAR_FILE, provider_status=provider)
    try:
        sample = PathSampler().sample(path)
    except OSError:
        return _pending(SyncReadyStatus.READ_ERROR, provider_status=provider)
    return _pending(
        SyncReadyStatus.DRY_RUN_METADATA_ONLY,
        size_bytes=sample.size_bytes,
        mtime_ns=sample.mtime_ns,
        provider_status=provider,
    )


def probe_sync_ready(
    path: Path,
    sampler: Sampler = PathSampler(),
    read_probe_timeout_seconds: float = READ_PROBE_TIMEOUT_SECONDS,
) -> SyncReadyResult:
    if not path.exists():
        return _pending(SyncReadyStatus.MISSING_PATH)
    if not path.is_file():
        return _pending(SyncReadyStatus.NOT_REGULAR_FILE)
    try:
        _read_probe_byte(path, read_probe_timeout_seconds)
        first = sampler.sample(path)
        second = sampler.sample(path)
    except SyncProbeTimeoutError:
        return _pending(SyncReadyStatus.READ_ERROR, provider_status="read_timeout")
    except OSError:
        return _pending(SyncReadyStatus.READ_ERROR)
    if first.size_bytes != second.size_bytes or first.mtime_ns != second.mtime_ns:
        return _pending(
            SyncReadyStatus.UNSTABLE_FILE,
            size_bytes=second.size_bytes,
            mtime_ns=second.mtime_ns,
        )
    try:
        payload = path.read_bytes()
    except OSError:
        return _pending(SyncReadyStatus.READ_ERROR)
    sha256 = hashlib.sha256(payload).hexdigest()
    if not payload.startswith(b"%PDF"):
        return _pending(
            SyncReadyStatus.INVALID_PDF_HEADER,
            sha256=sha256,
            size_bytes=second.size_bytes,
            mtime_ns=second.mtime_ns,
        )
    if not _minimal_pdf_parse_succeeds(payload):
        return _pending(
            SyncReadyStatus.INVALID_PDF_PARSE,
            sha256=sha256,
            size_bytes=second.size_bytes,
            mtime_ns=second.mtime_ns,
        )
    return SyncReadyResult(
        status=SyncReadyStatus.READY,
        sha256=sha256,
        size_bytes=second.size_bytes,
        mtime_ns=second.mtime_ns,
        retry_after_seconds=None,
    )


def _pending(
    status: SyncReadyStatus,
    *,
    sha256: str | None = None,
    size_bytes: int | None = None,
    mtime_ns: int | None = None,
    provider_status: str | None = None,
) -> SyncReadyResult:
    return SyncReadyResult(
        status=status,
        sha256=sha256,
        size_bytes=size_bytes,
        mtime_ns=mtime_ns,
        retry_after_seconds=RETRY_AFTER_SECONDS,
        provider_status=provider_status,
    )


def _minimal_pdf_parse_succeeds(payload: bytes) -> bool:
    if b"%%EOF" not in payload:
        return False
    if _has_uncompressed_page_tree(payload):
        return True
    return _has_compressed_pdf_structure(payload)


def _has_uncompressed_page_tree(payload: bytes) -> bool:
    return b"/Page" in payload or b"/Pages" in payload


def _has_compressed_pdf_structure(payload: bytes) -> bool:
    return b"startxref" in payload and (
        b"/ObjStm" in payload or b"/XRef" in payload or b"/Type /XRef" in payload
    )


def _read_probe_byte(path: Path, timeout_seconds: float) -> None:
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    signal.signal(signal.SIGALRM, _handle_probe_timeout)
    try:
        with path.open("rb") as handle:
            handle.read(1)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])
        signal.signal(signal.SIGALRM, previous_handler)


def _handle_probe_timeout(signum: int, frame: FrameType | None) -> None:
    _ = signum
    _ = frame
    raise SyncProbeTimeoutError
