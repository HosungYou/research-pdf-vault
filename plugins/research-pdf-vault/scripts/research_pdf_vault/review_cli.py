from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Protocol, TextIO, assert_never

from research_pdf_vault.config import ConfigLoadRequest, load_config
from research_pdf_vault.review_queue import (
    ReviewApprovalRequest,
    ReviewMergeRequest,
    ReviewMutationApplied,
    ReviewMutationMissing,
    ReviewMutationRefused,
    ReviewMutationRequest,
    initialize_review_database,
    list_review_items,
    review_approve,
    review_merge,
    review_reclassify,
    review_reject,
    show_review_item,
)
from research_pdf_vault.scan_db import now_timestamp
from research_pdf_vault.schema import Lane


class SubparserCollection(Protocol):
    def add_parser(self, name: str) -> argparse.ArgumentParser: ...


def add_review_parser(subparsers: SubparserCollection) -> None:
    review_parser = subparsers.add_parser("review")
    review_subparsers = review_parser.add_subparsers(
        dest="review_command",
        required=True,
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", type=Path)
    review_subparsers.add_parser("list", parents=(common,))
    show_parser = review_subparsers.add_parser("show", parents=(common,))
    show_parser.add_argument("identifier")
    approve_parser = review_subparsers.add_parser("approve", parents=(common,))
    _add_mutation_args(approve_parser)
    approve_parser.add_argument("--allow-sensitive", action="store_true")
    reject_parser = review_subparsers.add_parser("reject", parents=(common,))
    _add_mutation_args(reject_parser)
    reclassify_parser = review_subparsers.add_parser("reclassify", parents=(common,))
    _add_mutation_args(reclassify_parser)
    reclassify_parser.add_argument(
        "--lane",
        required=True,
        choices=tuple(lane.value for lane in Lane),
    )
    merge_parser = review_subparsers.add_parser("merge", parents=(common,))
    _add_mutation_args(merge_parser)
    merge_parser.add_argument("target_identifier")


def run_review(args: argparse.Namespace) -> int:
    config = load_config(ConfigLoadRequest(config_path=args.config))
    config.manifest_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.manifest_db) as connection:
        initialize_review_database(connection)
        match args.review_command:
            case "list":
                return _run_list(connection, config.approval.manual_review_lanes)
            case "show":
                return _run_show(
                    connection,
                    args.identifier,
                    config.approval.manual_review_lanes,
                )
            case "approve":
                return _run_approve(connection, args)
            case "reject":
                return _run_reject(connection, args)
            case "reclassify":
                return _run_reclassify(connection, args)
            case "merge":
                return _run_merge(connection, args)
            case _ as unreachable:
                assert_never(unreachable)


def _run_list(
    connection: sqlite3.Connection,
    manual_review_lanes: tuple[str, ...],
) -> int:
    items = list_review_items(connection, now_timestamp(), manual_review_lanes)
    if not items:
        print("review queue empty")
        return 0
    print("review queue:")
    for item in items:
        print(
            f"{item.queue_item_id}\t{item.paper_id}\t{item.lane.value}\t"
            f"{item.stage_status.value}\t{item.priority.value}\t{item.reason}",
        )
    return 0


def _run_show(
    connection: sqlite3.Connection,
    identifier: str,
    manual_review_lanes: tuple[str, ...],
) -> int:
    item = show_review_item(connection, identifier, now_timestamp(), manual_review_lanes)
    if item is None:
        print(f"error: review item not found: {identifier}", file=sys.stderr)
        return 1
    print(f"queue_item_id: {item.queue_item_id}")
    print(f"paper_id: {item.paper_id}")
    print(f"title: {item.title}")
    print(f"lane: {item.lane.value}")
    print(f"stage_status: {item.stage_status.value}")
    print(f"priority: {item.priority.value}")
    print(f"reason: {item.reason}")
    return 0


def _run_approve(connection: sqlite3.Connection, args: argparse.Namespace) -> int:
    result = review_approve(
        connection,
        ReviewApprovalRequest(
            mutation=_mutation_request(args),
            allow_sensitive=args.allow_sensitive,
        ),
    )
    return _print_mutation_result(result, sys.stderr)


def _run_reject(connection: sqlite3.Connection, args: argparse.Namespace) -> int:
    result = review_reject(connection, _mutation_request(args))
    return _print_mutation_result(result, sys.stderr)


def _run_reclassify(connection: sqlite3.Connection, args: argparse.Namespace) -> int:
    result = review_reclassify(connection, _mutation_request(args), Lane(args.lane))
    return _print_mutation_result(result, sys.stderr)


def _run_merge(connection: sqlite3.Connection, args: argparse.Namespace) -> int:
    result = review_merge(
        connection,
        ReviewMergeRequest(
            source=_mutation_request(args),
            target_identifier=args.target_identifier,
        ),
    )
    return _print_mutation_result(result, sys.stderr)


def _mutation_request(args: argparse.Namespace) -> ReviewMutationRequest:
    return ReviewMutationRequest(
        identifier=args.identifier,
        actor=args.actor,
        reason=args.reason,
        timestamp=now_timestamp(),
    )


def _print_mutation_result(
    result: ReviewMutationApplied | ReviewMutationRefused | ReviewMutationMissing,
    error_stream: TextIO,
) -> int:
    match result:
        case ReviewMutationApplied(item=item):
            print(
                f"review ok: {item.queue_item_id} {item.paper_id} "
                f"{item.lane.value} {item.stage_status.value}",
            )
            return 0
        case ReviewMutationRefused(paper_id=paper_id, reason=reason):
            print(f"error: review refused for {paper_id}: {reason}", file=error_stream)
            return 1
        case ReviewMutationMissing(identifier=identifier):
            print(f"error: review item not found: {identifier}", file=error_stream)
            return 1
        case _ as unreachable:
            assert_never(unreachable)


def _add_mutation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("identifier")
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reason", required=True)
