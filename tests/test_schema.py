from __future__ import annotations

import dataclasses
import json
import sqlite3
import sys
from pathlib import Path
from typing import TypeAlias

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

JsonValue: TypeAlias = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)
JsonObject: TypeAlias = dict[str, JsonValue]

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = ROOT / "schemas"
FIXTURE_DIR = ROOT / "fixtures" / "schema"
SCRIPTS_DIR = ROOT / "plugins" / "research-pdf-vault" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

SCHEMA_NAMES = (
    "vault_config",
    "paper",
    "paper_instance",
    "classification_decision",
    "review_queue_item",
    "audit_log",
    "extracted_passage",
    "claim_card",
    "citation_slot",
    "worker_report",
    "artifact_status",
)

EXPECTED_TABLE_NAMES = {
    "vault_config",
    "paper",
    "paper_instance",
    "classification_decision",
    "review_queue_item",
    "audit_log",
    "extracted_passage",
    "claim_card",
    "citation_slot",
    "worker_report",
    "artifact_status",
}
STALE_REVIEW_LANE = "yel" + "low"


def load_json(path: Path) -> JsonObject:
    data: JsonObject = json.loads(path.read_text(encoding="utf-8"))
    return data


def validator_for(schema_name: str) -> Draft202012Validator:
    schema_path = SCHEMAS_DIR / f"{schema_name}.schema.json"
    assert schema_path.exists(), f"missing schema file: {schema_path}"

    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_happy_fixture_rows_validate_against_canonical_json_schemas() -> None:
    for schema_name in SCHEMA_NAMES:
        fixture_path = FIXTURE_DIR / "happy" / f"{schema_name}.json"
        assert fixture_path.exists(), f"missing fixture file: {fixture_path}"

        validator = validator_for(schema_name)
        validator.validate(load_json(fixture_path))


def test_red_lane_vector_artifact_path_is_rejected_by_json_schema() -> None:
    validator = validator_for("artifact_status")
    bad_fixture = load_json(
        FIXTURE_DIR / "failure" / "red_lane_vector_artifact_path.json",
    )

    with pytest.raises(ValidationError):
        validator.validate(bad_fixture)


def test_lane_json_schemas_accept_amber_and_reject_stale_review_lane() -> None:
    for schema_name, lane_field in (
        ("vault_config", "default_lane"),
        ("paper", "lane"),
        ("classification_decision", "lane"),
        ("review_queue_item", "lane"),
        ("artifact_status", "lane"),
    ):
        validator = validator_for(schema_name)
        payload = load_json(FIXTURE_DIR / "happy" / f"{schema_name}.json")

        payload[lane_field] = "amber"
        validator.validate(payload)

        payload[lane_field] = STALE_REVIEW_LANE
        with pytest.raises(ValidationError):
            validator.validate(payload)


def test_schema_models_are_frozen_and_reject_red_lane_vector_paths() -> None:
    from research_pdf_vault.schema import (
        ArtifactDigest,
        ArtifactId,
        ArtifactKind,
        ArtifactStatus,
        Lane,
        NormalizedIdentifiers,
        Paper,
        PaperId,
        RepoRelativePath,
        SchemaVersion,
        StageStatus,
        Timestamp,
        VectorArtifactPolicyError,
        lane_can_carry_vector_path,
    )

    paper = Paper(
        schema_version=SchemaVersion("1.0.0"),
        paper_id=PaperId("paper_demo_001"),
        title="Synthetic Research Paper",
        normalized_identifiers=NormalizedIdentifiers(
            doi="10.0000/example.demo",
            arxiv_id="2501.00001",
            openalex_id="W000000001",
        ),
        lane=Lane.GREEN,
        created_at=Timestamp("2026-01-01T00:01:00Z"),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(paper, "title", "Changed")

    assert lane_can_carry_vector_path(Lane.AMBER) is True

    with pytest.raises(VectorArtifactPolicyError):
        ArtifactStatus(
            schema_version=SchemaVersion("1.0.0"),
            artifact_id=ArtifactId("artifact_red_vector_001"),
            paper_id=PaperId("paper_demo_001"),
            artifact_kind=ArtifactKind.VECTOR_INDEX,
            lane=Lane.RED,
            stage_status=StageStatus.COMPLETE,
            artifact_digest=ArtifactDigest(
                "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
            ),
            created_at=Timestamp("2026-01-01T00:40:00Z"),
            artifact_path=RepoRelativePath("fixtures/schema/artifacts/red.index"),
            vector_artifact_path=RepoRelativePath(
                "fixtures/schema/artifacts/red.vectors",
            ),
        )


def test_initialize_database_creates_canonical_tables() -> None:
    from research_pdf_vault.db import initialize_database

    with sqlite3.connect(":memory:") as connection:
        initialize_database(connection)
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'",
            )
        }

    assert EXPECTED_TABLE_NAMES <= table_names


def test_sqlite_accepts_amber_and_rejects_stale_lane_constraints() -> None:
    from research_pdf_vault.db import initialize_database

    with sqlite3.connect(":memory:") as connection:
        initialize_database(connection)
        for statement in (
            "INSERT INTO vault_config (schema_version, vault_id, root_path, created_at, default_lane) VALUES ('1.0.0', 'vault_amber', 'fixtures/schema/vault-root', '2026-01-01T00:00:00Z', 'amber')",
            "INSERT INTO paper (schema_version, paper_id, title, normalized_identifiers, lane, created_at) VALUES ('1.0.0', 'paper_demo_amber', 'Synthetic Research Paper', '{\"doi\":\"10.0000/example.demo\"}', 'amber', '2026-01-01T00:01:00Z')",
            "INSERT INTO classification_decision (schema_version, decision_id, paper_id, lane, stage_status, actor, timestamp, reason) VALUES ('1.0.0', 'decision_demo_amber', 'paper_demo_amber', 'amber', 'pending', 'schema_worker', '2026-01-01T00:03:00Z', 'Synthetic amber classification.')",
            "INSERT INTO review_queue_item (schema_version, queue_item_id, paper_id, lane, stage_status, priority, reason, created_at) VALUES ('1.0.0', 'queue_demo_amber', 'paper_demo_amber', 'amber', 'pending', 'normal', 'Synthetic row awaiting review.', '2026-01-01T00:04:00Z')",
            "INSERT INTO artifact_status (schema_version, artifact_id, paper_id, artifact_kind, lane, stage_status, artifact_digest, created_at, artifact_path, vector_artifact_path) VALUES ('1.0.0', 'artifact_demo_amber', 'paper_demo_amber', 'vector_index', 'amber', 'complete', 'sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd', '2026-01-01T00:40:00Z', 'fixtures/schema/artifacts/amber.index', 'fixtures/schema/artifacts/amber.vectors')",
        ):
            connection.execute(statement)
        for statement in (
            f"INSERT INTO vault_config (schema_version, vault_id, root_path, created_at, default_lane) VALUES ('1.0.0', 'vault_stale', 'fixtures/schema/vault-root', '2026-01-01T00:00:00Z', '{STALE_REVIEW_LANE}')",
            f"INSERT INTO paper (schema_version, paper_id, title, normalized_identifiers, lane, created_at) VALUES ('1.0.0', 'paper_demo_stale', 'Synthetic Research Paper', '{{}}', '{STALE_REVIEW_LANE}', '2026-01-01T00:01:00Z')",
            f"INSERT INTO classification_decision (schema_version, decision_id, paper_id, lane, stage_status, actor, timestamp, reason) VALUES ('1.0.0', 'decision_demo_stale', 'paper_demo_amber', '{STALE_REVIEW_LANE}', 'pending', 'schema_worker', '2026-01-01T00:03:00Z', 'Synthetic stale classification.')",
            f"INSERT INTO review_queue_item (schema_version, queue_item_id, paper_id, lane, stage_status, priority, reason, created_at) VALUES ('1.0.0', 'queue_demo_stale', 'paper_demo_amber', '{STALE_REVIEW_LANE}', 'pending', 'normal', 'Synthetic row awaiting review.', '2026-01-01T00:04:00Z')",
            f"INSERT INTO artifact_status (schema_version, artifact_id, paper_id, artifact_kind, lane, stage_status, artifact_digest, created_at) VALUES ('1.0.0', 'artifact_demo_stale', 'paper_demo_amber', 'metadata', '{STALE_REVIEW_LANE}', 'complete', 'sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee', '2026-01-01T00:40:00Z')",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(statement)


def test_sqlite_rejects_red_lane_vector_artifact_path() -> None:
    from research_pdf_vault.db import initialize_database

    with sqlite3.connect(":memory:") as connection:
        initialize_database(connection)
        connection.execute(
            "INSERT INTO paper ("
            "schema_version, paper_id, title, normalized_identifiers, lane, "
            "created_at"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "paper_demo_001",
                "Synthetic Research Paper",
                '{"doi":"10.0000/example.demo"}',
                "red",
                "2026-01-01T00:01:00Z",
            ),
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO artifact_status ("
                "schema_version, artifact_id, paper_id, artifact_kind, lane, "
                "stage_status, artifact_digest, created_at, artifact_path, "
                "vector_artifact_path"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "1.0.0",
                    "artifact_red_vector_001",
                    "paper_demo_001",
                    "vector_index",
                    "red",
                    "complete",
                    "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
                    "2026-01-01T00:40:00Z",
                    "fixtures/schema/artifacts/red.index",
                    "fixtures/schema/artifacts/red.vectors",
                ),
            )


def test_sqlite_rejects_paper_id_updates() -> None:
    from research_pdf_vault.db import initialize_database

    with sqlite3.connect(":memory:") as connection:
        initialize_database(connection)
        connection.execute(
            "INSERT INTO paper ("
            "schema_version, paper_id, title, normalized_identifiers, lane, "
            "created_at"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (
                "1.0.0",
                "paper_demo_001",
                "Synthetic Research Paper",
                '{"doi":"10.0000/example.demo"}',
                "green",
                "2026-01-01T00:01:00Z",
            ),
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE paper SET paper_id = ? WHERE paper_id = ?",
                ("paper_demo_renamed", "paper_demo_001"),
            )
