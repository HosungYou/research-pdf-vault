from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Protocol, assert_never

from research_pdf_vault.config import ConfigLoadRequest, load_config
from research_pdf_vault.literature_map import (
    build_literature_map,
    literature_map_report,
)


class SubparserCollection(Protocol):
    def add_parser(self, name: str) -> argparse.ArgumentParser: ...


def add_literature_map_parser(subparsers: SubparserCollection) -> None:
    parser = subparsers.add_parser("literature-map")
    nested = parser.add_subparsers(dest="literature_command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", type=Path)
    nested.add_parser("build", parents=(common,))
    nested.add_parser("report", parents=(common,))


def run_literature_map(args: argparse.Namespace) -> int:
    config = load_config(ConfigLoadRequest(config_path=args.config))
    match args.literature_command:
        case "build":
            summary = build_literature_map(config)
            print(
                "literature-map ok: "
                f"nodes={summary.node_count} edges={summary.edge_count}",
            )
            return 0
        case "report":
            print(json.dumps(literature_map_report(config), indent=2, sort_keys=True))
            return 0
        case _ as unreachable:
            assert_never(unreachable)
