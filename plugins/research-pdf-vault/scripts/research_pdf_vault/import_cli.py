from __future__ import annotations

import re
import shutil
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol
from uuid import uuid4

from research_pdf_vault.config import ConfigLoadRequest, VaultRuntimeConfig, load_config
from research_pdf_vault.db import SCHEMA_VERSION
from research_pdf_vault.scan_db import initialize_scan_database, now_timestamp
from research_pdf_vault.sync_ready import SyncReadyStatus, probe_sync_ready

IMPORT_SQL: Final = (
    "CREATE TABLE IF NOT EXISTS import_event ("
    "schema_version TEXT NOT NULL CHECK (schema_version = '1.0.0'), "
    "import_event_id TEXT PRIMARY KEY CHECK (import_event_id GLOB 'import_*'), "
    "sha256 TEXT NOT NULL CHECK (length(sha256) = 64), "
    "source_label TEXT NOT NULL CHECK (length(source_label) > 0), "
    "doi TEXT, "
    "actor TEXT NOT NULL CHECK (length(actor) > 0), "
    "target_path TEXT NOT NULL CHECK (length(target_path) > 0 AND target_path NOT GLOB '/*' AND target_path != '..' AND target_path NOT GLOB '../*' AND target_path NOT GLOB '*/../*'), "
    "event_status TEXT NOT NULL CHECK (event_status IN ('imported', 'existing')), "
    "created_at TEXT NOT NULL"
    ");"
)
_SLUG_RE: Final = re.compile(r"[a-z0-9]+")


class ImportSubparserCollection(Protocol):
    def add_parser(self, name: str) -> object: ...


@dataclass(frozen=True, slots=True)
class PdfImportError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class ImportRequest:
    source_path: Path
    config: VaultRuntimeConfig
    title: str | None
    doi: str | None
    source_label: str
    actor: str


@dataclass(frozen=True, slots=True)
class ImportResult:
    status: str
    sha256: str
    relative_path: str
    import_event_id: str


def add_import_parser(subparsers) -> None:
    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("pdf_path", type=Path)
    import_parser.add_argument("--config", type=Path)
    import_parser.add_argument("--title")
    import_parser.add_argument("--doi")
    import_parser.add_argument("--source", default="local-file")
    import_parser.add_argument("--actor", default="codex")


def run_import(args) -> int:
    config = load_config(ConfigLoadRequest(config_path=args.config))
    result = import_pdf(
        ImportRequest(
            source_path=args.pdf_path,
            config=config,
            title=args.title,
            doi=args.doi,
            source_label=args.source,
            actor=args.actor,
        ),
    )
    print(
        "import ok: "
        f"status={result.status} "
        f"sha256={result.sha256} "
        f"relative_path={result.relative_path} "
        f"event_id={result.import_event_id}",
    )
    return 0


def import_pdf(request: ImportRequest) -> ImportResult:
    source_path = request.source_path.expanduser().resolve()
    _validate_source_path(source_path)
    result = probe_sync_ready(source_path)
    match result.status:
        case SyncReadyStatus.READY:
            pass
        case (
            SyncReadyStatus.DRY_RUN_METADATA_ONLY
            | SyncReadyStatus.MISSING_PATH
            | SyncReadyStatus.NOT_REGULAR_FILE
            | SyncReadyStatus.READ_ERROR
            | SyncReadyStatus.UNSTABLE_FILE
            | SyncReadyStatus.INVALID_PDF_HEADER
            | SyncReadyStatus.INVALID_PDF_PARSE
        ):
            raise PdfImportError(f"PDF is not import-ready: {result.status.value}")
    if result.sha256 is None:
        raise PdfImportError("PDF is ready but no sha256 was produced")

    inbox = _inbox_path(request.config)
    inbox.mkdir(parents=True, exist_ok=True)
    target = inbox / _target_filename(result.sha256, request.title, source_path)
    status = _copy_into_inbox(source_path, target)
    relative_path = _relative_import_path(request.config, target)
    import_event_id = _record_import_event(request, result.sha256, relative_path, status)
    return ImportResult(
        status=status,
        sha256=result.sha256,
        relative_path=relative_path,
        import_event_id=import_event_id,
    )


def _validate_source_path(source_path: Path) -> None:
    if not source_path.exists():
        raise PdfImportError(f"source PDF does not exist: {source_path}")
    if not source_path.is_file():
        raise PdfImportError(f"source path is not a file: {source_path}")
    if source_path.suffix.lower() != ".pdf":
        raise PdfImportError("source path must end with .pdf")


def _inbox_path(config: VaultRuntimeConfig) -> Path:
    if len(config.storage_roots) == 0:
        raise PdfImportError("config has no storage_roots for import")
    return config.storage_roots[0] / "inbox"


def _target_filename(sha256: str, title: str | None, source_path: Path) -> str:
    label = title if title is not None else source_path.stem
    return f"{sha256}-{_slug(label)}.pdf"


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore")
    words = _SLUG_RE.findall(normalized.decode("ascii").lower())
    if len(words) == 0:
        return "imported-paper"
    return "-".join(words)[:96].strip("-")


def _copy_into_inbox(source_path: Path, target: Path) -> str:
    if target.exists():
        return "existing"
    temporary = target.with_name(f".{target.name}.tmp-{uuid4().hex}")
    try:
        shutil.copy2(source_path, temporary)
        temporary.replace(target)
    except OSError as error:
        if temporary.exists():
            temporary.unlink()
        raise PdfImportError(f"failed to import PDF: {error}") from error
    return "imported"


def _relative_import_path(config: VaultRuntimeConfig, target: Path) -> str:
    root = config.storage_roots[0]
    relative = target.resolve().relative_to(root.resolve())
    return (Path(root.name) / relative).as_posix()


def _record_import_event(
    request: ImportRequest,
    sha256: str,
    relative_path: str,
    status: str,
) -> str:
    import_event_id = f"import_{uuid4().hex[:24]}"
    request.config.manifest_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(request.config.manifest_db) as connection:
        initialize_scan_database(connection)
        connection.execute(IMPORT_SQL)
        connection.execute(
            "INSERT INTO import_event (schema_version, import_event_id, sha256, source_label, doi, actor, target_path, event_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                SCHEMA_VERSION,
                import_event_id,
                sha256,
                request.source_label,
                request.doi,
                request.actor,
                relative_path,
                status,
                now_timestamp(),
            ),
        )
    return import_event_id
