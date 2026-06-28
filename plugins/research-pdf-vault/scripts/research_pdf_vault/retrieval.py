from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum, unique
from pathlib import Path
from typing import Final, TypeAlias, TypeGuard

from research_pdf_vault.schema import PaperId, PassageId

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
PASSAGES_FILE: Final = "passages.json"


@unique
class TaskSupportTag(StrEnum):
    DIRECT_SUPPORT = "direct_support"
    ANALOGY_ONLY = "analogy_only"
    GAP = "gap"


@dataclass(frozen=True, slots=True)
class CitationFixtureError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class RetrievedPassage:
    passage_id: PassageId
    paper_id: PaperId
    source: str
    page: int | None
    location: str
    start_offset: int
    end_offset: int
    passage: str
    proposed_claim: str
    support_tag: TaskSupportTag
    confidence: float
    gap_reason: str


def retrieve_fixture_passages(
    fixture_root: Path,
    project: str,
) -> tuple[RetrievedPassage, ...]:
    fixture_path = fixture_root / project / PASSAGES_FILE
    raw_fixture = _read_json(fixture_path)
    return _passages_from_fixture(raw_fixture, project)


def _read_json(path: Path) -> JsonValue:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise CitationFixtureError(f"invalid citation fixture JSON: {path}") from error


def _passages_from_fixture(
    raw_fixture: JsonValue,
    expected_project: str,
) -> tuple[RetrievedPassage, ...]:
    fixture = _required_object(raw_fixture, "citation fixture")
    project = _required_str(fixture, "project")
    if project != expected_project:
        raise CitationFixtureError(
            f"citation fixture project mismatch: expected {expected_project}, got {project}",
        )
    raw_passages = fixture.get("passages")
    if not _is_json_list(raw_passages):
        raise CitationFixtureError("passages must be a list")
    return tuple(
        _passage_from_object(_required_object(value, "passage"))
        for value in raw_passages
    )


def _passage_from_object(raw_passage: JsonObject) -> RetrievedPassage:
    return RetrievedPassage(
        passage_id=PassageId(_required_str(raw_passage, "passage_id")),
        paper_id=PaperId(_required_str(raw_passage, "paper_id")),
        source=_required_str(raw_passage, "source"),
        page=_optional_page(raw_passage),
        location=_required_str(raw_passage, "location"),
        start_offset=_required_int(raw_passage, "start_offset"),
        end_offset=_required_int(raw_passage, "end_offset"),
        passage=_required_str(raw_passage, "passage"),
        proposed_claim=_required_str(raw_passage, "proposed_claim"),
        support_tag=_support_tag(_required_str(raw_passage, "support_tag")),
        confidence=_required_float(raw_passage, "confidence"),
        gap_reason=_required_str(raw_passage, "gap_reason"),
    )


def _required_object(value: JsonValue, field_name: str) -> JsonObject:
    if _is_json_object(value):
        return value
    raise CitationFixtureError(f"{field_name} must be an object")


def _required_str(raw_object: JsonObject, field_name: str) -> str:
    raw_value = raw_object.get(field_name)
    if type(raw_value) is str:
        if raw_value or field_name == "gap_reason":
            return raw_value
        raise CitationFixtureError(f"{field_name} must not be empty")
    raise CitationFixtureError(f"{field_name} must be a string")


def _required_int(raw_object: JsonObject, field_name: str) -> int:
    raw_value = raw_object.get(field_name)
    if type(raw_value) is int:
        return raw_value
    raise CitationFixtureError(f"{field_name} must be an integer")


def _required_float(raw_object: JsonObject, field_name: str) -> float:
    raw_value = raw_object.get(field_name)
    if type(raw_value) is int:
        return float(raw_value)
    if type(raw_value) is float:
        return raw_value
    raise CitationFixtureError(f"{field_name} must be a number")


def _optional_page(raw_object: JsonObject) -> int | None:
    raw_value = raw_object.get("page")
    if raw_value is None:
        return None
    if type(raw_value) is int:
        return raw_value
    raise CitationFixtureError("page must be an integer or null")


def _support_tag(raw_value: str) -> TaskSupportTag:
    try:
        return TaskSupportTag(raw_value)
    except ValueError as error:
        raise CitationFixtureError(f"unknown support_tag: {raw_value}") from error


def _is_json_object(value: JsonValue) -> TypeGuard[JsonObject]:
    return type(value) is dict


def _is_json_list(value: JsonValue) -> TypeGuard[list[JsonValue]]:
    return type(value) is list
