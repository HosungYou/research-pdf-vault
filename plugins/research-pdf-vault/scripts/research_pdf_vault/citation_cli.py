from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Protocol, TypedDict

from research_pdf_vault.citation_slots import (
    CitationSlotOutput,
    build_citation_slots,
    citation_slots_to_output,
)
from research_pdf_vault.claim_cards import (
    ClaimCardOutput,
    build_claim_cards,
    claim_cards_to_output,
)
from research_pdf_vault.config import ConfigLoadRequest, load_config
from research_pdf_vault.retrieval import retrieve_fixture_passages


class SubparserCollection(Protocol):
    def add_parser(self, name: str) -> argparse.ArgumentParser: ...


class CitationBuildOutput(TypedDict):
    project: str
    claim_cards: list[ClaimCardOutput]
    citation_slots: list[CitationSlotOutput]


def add_citation_slots_parser(subparsers: SubparserCollection) -> None:
    parser = subparsers.add_parser("citation-slots")
    commands = parser.add_subparsers(dest="citation_slots_command", required=True)
    build_parser = commands.add_parser("build")
    build_parser.add_argument("--config", type=Path, required=True)
    build_parser.add_argument("--project", required=True)


def run_citation_slots(args: argparse.Namespace) -> int:
    if args.citation_slots_command == "build":
        return _run_build(args)
    return 1


def _run_build(args: argparse.Namespace) -> int:
    config = load_config(ConfigLoadRequest(config_path=args.config))
    project = str(args.project)
    passages = retrieve_fixture_passages(_fixture_root_for_config(config.config_path), project)
    cards = build_claim_cards(passages)
    slots = build_citation_slots(cards)
    payload: CitationBuildOutput = {
        "project": project,
        "claim_cards": claim_cards_to_output(cards),
        "citation_slots": citation_slots_to_output(slots),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _fixture_root_for_config(config_path: Path) -> Path:
    fixtures_dir = config_path.parent.parent
    if fixtures_dir.name == "fixtures":
        return fixtures_dir / "citations"
    return Path.cwd() / "fixtures" / "citations"
