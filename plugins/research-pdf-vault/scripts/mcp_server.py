#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
# --- How to run ---
# python3 plugins/research-pdf-vault/scripts/mcp_server.py --self-test --config fixtures/config/sample-config.toml
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

sys.dont_write_bytecode = True

from research_pdf_vault.config import ConfigValidationError
from research_pdf_vault.mcp_protocol import run_stdio_server
from research_pdf_vault.mcp_self_test import build_self_test_payload
from research_pdf_vault.mcp_tools import McpToolRunner
from research_pdf_vault.mcp_types import McpToolError


@dataclass(frozen=True, slots=True)
class CliOptions:
    self_test: bool
    config_path: Path | None
    help_requested: bool


def parse_cli(argv: Sequence[str]) -> CliOptions:
    self_test = False
    config_path: Path | None = None
    help_requested = False
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument == "--self-test":
            self_test = True
            index += 1
        elif argument == "--config":
            if index + 1 >= len(argv):
                raise McpToolError("--config requires a path")
            config_path = Path(argv[index + 1])
            index += 2
        elif argument in ("--help", "-h"):
            help_requested = True
            index += 1
        else:
            raise McpToolError(f"unknown argument: {argument}")
    return CliOptions(
        self_test=self_test,
        config_path=config_path,
        help_requested=help_requested,
    )


def main(argv: Sequence[str] | None = None) -> int:
    selected_argv = sys.argv[1:] if argv is None else argv
    try:
        options = parse_cli(selected_argv)
        if options.help_requested:
            print("usage: mcp_server.py [--config PATH] [--self-test]")
            return 0
        if options.self_test:
            print(json.dumps(build_self_test_payload(options.config_path), indent=2))
            return 0
        runner = McpToolRunner.from_config_path(options.config_path)
        run_stdio_server(runner, sys.stdin, sys.stdout)
        return 0
    except (ConfigValidationError, McpToolError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
