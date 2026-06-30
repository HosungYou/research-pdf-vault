from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Protocol, assert_never

from research_pdf_vault.config import ConfigLoadRequest, VaultRuntimeConfig, load_config
from research_pdf_vault.constructs import (
    build_construct_candidates,
    construct_report_json,
)
from research_pdf_vault.constructs_export import export_construct_registry
from research_pdf_vault.constructs_review import (
    ConstructReviewAction,
    approve_candidate,
    list_review_candidates,
    reassign_candidate,
    reject_candidate,
)


class SubparserCollection(Protocol):
    def add_parser(self, name: str) -> argparse.ArgumentParser: ...


def add_constructs_parser(subparsers: SubparserCollection) -> None:
    parser = subparsers.add_parser("constructs")
    nested = parser.add_subparsers(dest="constructs_command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", type=Path)
    nested.add_parser("build", parents=(common,))
    nested.add_parser("export", parents=(common,))
    nested.add_parser("report", parents=(common,))
    review_parser = nested.add_parser("review")
    review_nested = review_parser.add_subparsers(dest="review_command", required=True)
    review_nested.add_parser("list", parents=(common,))
    for action_name in ("approve", "reject"):
        action_parser = review_nested.add_parser(action_name, parents=(common,))
        action_parser.add_argument("candidate_id")
        action_parser.add_argument("--actor", required=True)
        action_parser.add_argument("--reason", required=True)
    reassign_parser = review_nested.add_parser("reassign", parents=(common,))
    reassign_parser.add_argument("candidate_id")
    reassign_parser.add_argument("--construct", required=True)
    reassign_parser.add_argument("--actor", required=True)
    reassign_parser.add_argument("--reason", required=True)


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
        case "export":
            result = export_construct_registry(config)
            print(
                "constructs export ok: "
                f"registry={result.registry_count} "
                f"candidates={result.candidate_count} "
                f"jsonl={result.jsonl_path} "
                f"markdown={result.markdown_path}",
            )
            return 0
        case "report":
            print(json.dumps(construct_report_json(config), indent=2, sort_keys=True))
            return 0
        case "review":
            return _run_construct_review(args, config)
        case _ as unreachable:
            assert_never(unreachable)


def _run_construct_review(args: argparse.Namespace, config: VaultRuntimeConfig) -> int:
    match args.review_command:
        case "list":
            rows = list_review_candidates(config)
            if rows:
                print("\n".join(rows))
            else:
                print("construct review empty")
            return 0
        case "approve":
            result = approve_candidate(config, _review_action(args))
        case "reject":
            result = reject_candidate(config, _review_action(args))
        case "reassign":
            result = reassign_candidate(
                config,
                _review_action(args, target_construct_id=args.construct),
            )
        case _ as unreachable:
            assert_never(unreachable)
    print(
        "construct review ok: "
        f"action={result.action} "
        f"candidate_id={result.candidate_id}",
    )
    return 0


def _review_action(
    args: argparse.Namespace,
    target_construct_id: str | None = None,
) -> ConstructReviewAction:
    return ConstructReviewAction(
        candidate_id=args.candidate_id,
        actor=args.actor,
        reason=args.reason,
        target_construct_id=target_construct_id,
    )
