from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Protocol, assert_never

from research_pdf_vault.config import ConfigLoadRequest, load_config
from research_pdf_vault.constructs import (
    build_construct_candidates,
    construct_report_json,
)


class SubparserCollection(Protocol):
    def add_parser(self, name: str) -> argparse.ArgumentParser: ...


def add_constructs_parser(subparsers: SubparserCollection) -> None:
    parser = subparsers.add_parser("constructs")
    nested = parser.add_subparsers(dest="constructs_command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", type=Path)
    nested.add_parser("build", parents=(common,))
    nested.add_parser("report", parents=(common,))


def run_constructs(args: argparse.Namespace) -> int:
    config = load_config(ConfigLoadRequest(config_path=args.config))
    match args.constructs_command:
        case "build":
            summary = build_construct_candidates(config)
            print(
                "constructs ok: "
                f"registry={summary.registry_count} "
                f"candidates={summary.candidate_count} "
                f"review_required={summary.review_required_count}",
            )
            return 0
        case "report":
            print(json.dumps(construct_report_json(config), indent=2, sort_keys=True))
            return 0
        case _ as unreachable:
            assert_never(unreachable)
