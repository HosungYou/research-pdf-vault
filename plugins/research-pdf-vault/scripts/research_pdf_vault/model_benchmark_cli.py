from __future__ import annotations

import argparse
import json
import sys
from typing import Protocol, assert_never

from research_pdf_vault.model_benchmark import (
    ModelBenchmarkRefused,
    benchmark_dry_run,
    profiles_payload,
)


class SubparserCollection(Protocol):
    def add_parser(self, name: str) -> argparse.ArgumentParser: ...


def add_model_benchmark_parser(subparsers: SubparserCollection) -> None:
    parser = subparsers.add_parser("model-benchmark")
    nested = parser.add_subparsers(dest="model_benchmark_command", required=True)
    nested.add_parser("profiles")
    run_parser = nested.add_parser("run")
    run_parser.add_argument("--profile", required=True)
    run_parser.add_argument("--dry-run", action="store_true", required=True)
    run_parser.add_argument("--allow-heavy", action="store_true")


def run_model_benchmark(args: argparse.Namespace) -> int:
    match args.model_benchmark_command:
        case "profiles":
            print(json.dumps(profiles_payload(), indent=2, sort_keys=True))
            return 0
        case "run":
            return _run_profile(args)
        case _ as unreachable:
            assert_never(unreachable)


def _run_profile(args: argparse.Namespace) -> int:
    try:
        payload = benchmark_dry_run(args.profile, allow_heavy=args.allow_heavy)
    except ModelBenchmarkRefused as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0
