#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Protocol, Sequence

sys.dont_write_bytecode = True

from _runtime_guard import ensure_supported_python

ensure_supported_python()

from research_pdf_vault.config import (
    ConfigLoadRequest,
    ConfigValidationError,
    default_config_path,
    load_config,
    write_default_config,
)
from research_pdf_vault.citation_cli import (
    add_citation_slots_parser,
    run_citation_slots,
)
from research_pdf_vault.embeddings import EmbeddingBackendError
from research_pdf_vault.fts import FtsUnavailableError
from research_pdf_vault.index_build import build_local_index
from research_pdf_vault.import_cli import (
    PdfImportError,
    add_import_parser,
    run_import,
)
from research_pdf_vault.literature_cli import (
    add_literature_map_parser,
    run_literature_map,
)
from research_pdf_vault.mcp_manifest import get_manifest_summary
from research_pdf_vault.model_benchmark_cli import (
    add_model_benchmark_parser,
    run_model_benchmark,
)
from research_pdf_vault.notify_cli import add_notify_parser, run_notify
from research_pdf_vault.retrieval import CitationFixtureError
from research_pdf_vault.scanner import run_one_shot_scan


class SubparserCollection(Protocol):
    def add_parser(self, name: str) -> argparse.ArgumentParser: ...


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rpv")
    subparsers = parser.add_subparsers(dest="command", required=True)
    setup_parser = subparsers.add_parser("setup")
    mode = setup_parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--init", action="store_true")
    mode.add_argument("--check", action="store_true")
    setup_parser.add_argument("--config", type=Path)
    setup_parser.add_argument("--force", action="store_true")
    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("--config", type=Path)
    scan_parser.add_argument("--once", action="store_true", required=True)
    scan_parser.add_argument("--dry-run", action="store_true")
    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("--config", type=Path)
    ingest_parser.add_argument("--once", action="store_true", required=True)
    add_import_parser(subparsers)
    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--config", type=Path)
    add_citation_slots_parser(subparsers)
    add_optional_review_parser(subparsers)
    add_notify_parser(subparsers)
    add_literature_map_parser(subparsers)
    add_model_benchmark_parser(subparsers)
    return parser


def add_optional_review_parser(subparsers: SubparserCollection) -> None:
    try:
        from research_pdf_vault.review_cli import add_review_parser
    except ModuleNotFoundError:
        subparsers.add_parser("review")
        return
    add_review_parser(subparsers)


def run_setup(args: argparse.Namespace) -> int:
    config_path = args.config if args.config is not None else default_config_path()
    if args.init:
        written_path = write_default_config(config_path, force=args.force)
        print(f"wrote config: {written_path}")
        return 0
    config = load_config(ConfigLoadRequest(config_path=args.config))
    print(f"config ok: {config.config_path}")
    print(f"cache_root: {config.cache_root}")
    print(f"manifest_db: {config.manifest_db}")
    return 0


def run_scan(args: argparse.Namespace) -> int:
    config = load_config(ConfigLoadRequest(config_path=args.config))
    summary = run_one_shot_scan(config, dry_run=args.dry_run)
    print(
        "scan ok: "
        f"scanned={summary.scanned_count} "
        f"ready={summary.ready_count} "
        f"pending={summary.pending_count} "
        f"dry_run={summary.dry_run_count}",
    )
    return 0


def run_ingest(args: argparse.Namespace) -> int:
    config = load_config(ConfigLoadRequest(config_path=args.config))
    scan_summary = run_one_shot_scan(config)
    index_summary = build_local_index(config)
    print(
        "ingest ok: "
        f"scanned={scan_summary.scanned_count} "
        f"ready={scan_summary.ready_count} "
        f"pending={scan_summary.pending_count}",
    )
    print(
        "index ok: "
        f"indexed={index_summary.indexed_count} "
        f"chunks={index_summary.chunk_count} "
        f"vectors={index_summary.vector_count} "
        f"quarantined={index_summary.quarantined_count} "
        f"skipped={index_summary.skipped_count}",
    )
    return 0


def run_report(args: argparse.Namespace) -> int:
    config = load_config(ConfigLoadRequest(config_path=args.config))
    print(json.dumps(get_manifest_summary(config), indent=2, sort_keys=True))
    return 0


def run_optional_review(args: argparse.Namespace) -> int:
    try:
        from research_pdf_vault.review_cli import run_review
    except ModuleNotFoundError as error:
        print(f"error: review CLI unavailable: {error}", file=sys.stderr)
        return 1
    return run_review(args)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "setup":
            return run_setup(args)
        if args.command == "scan":
            return run_scan(args)
        if args.command == "ingest":
            return run_ingest(args)
        if args.command == "import":
            return run_import(args)
        if args.command == "report":
            return run_report(args)
        if args.command == "citation-slots":
            return run_citation_slots(args)
        if args.command == "review":
            return run_optional_review(args)
        if args.command == "notify":
            return run_notify(args)
        if args.command == "literature-map":
            return run_literature_map(args)
        if args.command == "model-benchmark":
            return run_model_benchmark(args)
        parser.error(f"unknown command: {args.command}")
    except ConfigValidationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except (EmbeddingBackendError, FtsUnavailableError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except CitationFixtureError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except PdfImportError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
