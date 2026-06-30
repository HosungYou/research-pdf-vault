from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
RPV: Final = SCRIPTS_DIR / "rpv.py"
TEXT_PDF_BYTES: Final = (
    b"%PDF-1.4\n"
    b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
    b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
    b"3 0 obj << /Type /Page /Parent 2 0 R >> endobj\n"
    b"%%RPV_PAGE 1\n"
    b"Research article methods and results.\n"
    b"Construct: AI acceptance | Measurement: UTAUT survey scale | Role: outcome\n"
    b"Construct: perceived usefulness | Measurement: TAM usefulness items | Role: antecedent\n"
    b"%%RPV_END_PAGE\n"
    b"%%EOF\n"
)


def test_constructs_build_when_indexed_text_has_markers_then_records_candidates(
    tmp_path: Path,
) -> None:
    # Given
    library = tmp_path / "library"
    library.mkdir()
    (library / "constructs.pdf").write_bytes(TEXT_PDF_BYTES)
    config_path = tmp_path / "rpv.toml"
    config_path.write_text(_config_text(), encoding="utf-8")
    manifest_db = tmp_path / "cache" / "manifest.sqlite3"

    # When
    ingest = _run_rpv("ingest", "--once", "--config", str(config_path), cwd=tmp_path)
    build = _run_rpv("constructs", "build", "--config", str(config_path), cwd=tmp_path)
    report = _run_rpv("constructs", "report", "--config", str(config_path), cwd=tmp_path)

    # Then
    assert ingest.returncode == 0, ingest.stderr
    assert build.returncode == 0, build.stderr
    assert "constructs ok: registry=2 candidates=2 review_required=0" in build.stdout
    assert report.returncode == 0, report.stderr
    payload = json.loads(report.stdout)
    assert payload["registry_count"] == 2
    assert payload["candidate_count"] == 2
    assert payload["review_required_count"] == 0
    assert _candidate_rows(manifest_db) == [
        ("AI acceptance", "ai acceptance", "UTAUT survey scale", "outcome", 0),
        (
            "perceived usefulness",
            "perceived usefulness",
            "TAM usefulness items",
            "antecedent",
            0,
        ),
    ]


def test_literature_map_build_when_construct_candidates_exist_then_adds_edges(
    tmp_path: Path,
) -> None:
    # Given
    library = tmp_path / "library"
    library.mkdir()
    (library / "constructs.pdf").write_bytes(TEXT_PDF_BYTES)
    config_path = tmp_path / "rpv.toml"
    config_path.write_text(_config_text(), encoding="utf-8")

    # When
    ingest = _run_rpv("ingest", "--once", "--config", str(config_path), cwd=tmp_path)
    constructs = _run_rpv(
        "constructs",
        "build",
        "--config",
        str(config_path),
        cwd=tmp_path,
    )
    literature = _run_rpv(
        "literature-map",
        "build",
        "--config",
        str(config_path),
        cwd=tmp_path,
    )
    report = _run_rpv(
        "literature-map",
        "report",
        "--config",
        str(config_path),
        cwd=tmp_path,
    )

    # Then
    assert ingest.returncode == 0, ingest.stderr
    assert constructs.returncode == 0, constructs.stderr
    assert literature.returncode == 0, literature.stderr
    payload = json.loads(report.stdout)
    assert payload["node_counts"] == {"construct": 2, "paper": 1}
    assert payload["edge_counts"] == {"measures_construct": 2}


def test_constructs_export_when_candidates_exist_then_writes_jsonl_and_markdown(
    tmp_path: Path,
) -> None:
    # Given
    library = tmp_path / "library"
    library.mkdir()
    (library / "constructs.pdf").write_bytes(TEXT_PDF_BYTES)
    config_path = tmp_path / "rpv.toml"
    config_path.write_text(_config_text(), encoding="utf-8")
    jsonl_path = tmp_path / "cache" / "exports" / "construct_registry.jsonl"
    markdown_path = tmp_path / "cache" / "exports" / "construct_registry.md"

    # When
    ingest = _run_rpv("ingest", "--once", "--config", str(config_path), cwd=tmp_path)
    build = _run_rpv("constructs", "build", "--config", str(config_path), cwd=tmp_path)
    export = _run_rpv("constructs", "export", "--config", str(config_path), cwd=tmp_path)

    # Then
    assert ingest.returncode == 0, ingest.stderr
    assert build.returncode == 0, build.stderr
    assert export.returncode == 0, export.stderr
    assert f"jsonl={jsonl_path}" in export.stdout
    assert f"markdown={markdown_path}" in export.stdout
    rows = [
        json.loads(line)
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [row["canonical_label"] for row in rows] == [
        "ai acceptance",
        "perceived usefulness",
    ]
    assert rows[0]["candidates"][0]["reported_term"] == "AI acceptance"
    assert rows[0]["candidates"][0]["theoretical_role"] == "outcome"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Construct Registry" in markdown
    assert "## ai acceptance" in markdown
    assert "UTAUT survey scale" in markdown


def test_constructs_review_approve_when_candidate_requires_review_then_marks_approved(
    tmp_path: Path,
) -> None:
    # Given
    config_path = _prepared_construct_vault(tmp_path)
    manifest_db = tmp_path / "cache" / "manifest.sqlite3"
    candidate_id = _first_candidate_id(manifest_db)
    _mark_candidate_for_review(manifest_db, candidate_id)

    # When
    listed = _run_rpv(
        "constructs",
        "review",
        "list",
        "--config",
        str(config_path),
        cwd=tmp_path,
    )
    approved = _run_rpv(
        "constructs",
        "review",
        "approve",
        candidate_id,
        "--config",
        str(config_path),
        "--actor",
        "tester",
        "--reason",
        "construct verified",
        cwd=tmp_path,
    )

    # Then
    assert listed.returncode == 0, listed.stderr
    assert candidate_id in listed.stdout
    assert "AI acceptance" in listed.stdout
    assert approved.returncode == 0, approved.stderr
    assert f"construct review ok: action=approve candidate_id={candidate_id}" in approved.stdout
    assert _candidate_review_state(manifest_db, candidate_id) == ("approved", 0)


def test_constructs_review_reject_when_candidate_is_wrong_then_marks_rejected(
    tmp_path: Path,
) -> None:
    # Given
    config_path = _prepared_construct_vault(tmp_path)
    manifest_db = tmp_path / "cache" / "manifest.sqlite3"
    candidate_id = _first_candidate_id(manifest_db)
    _mark_candidate_for_review(manifest_db, candidate_id)

    # When
    rejected = _run_rpv(
        "constructs",
        "review",
        "reject",
        candidate_id,
        "--config",
        str(config_path),
        "--actor",
        "tester",
        "--reason",
        "not a construct",
        cwd=tmp_path,
    )

    # Then
    assert rejected.returncode == 0, rejected.stderr
    assert f"construct review ok: action=reject candidate_id={candidate_id}" in rejected.stdout
    assert _candidate_review_state(manifest_db, candidate_id) == ("rejected", 0)


def test_constructs_review_reassign_when_target_construct_exists_then_moves_candidate(
    tmp_path: Path,
) -> None:
    # Given
    config_path = _prepared_construct_vault(tmp_path)
    manifest_db = tmp_path / "cache" / "manifest.sqlite3"
    candidate_id = _first_candidate_id(manifest_db)
    target_construct_id = _last_construct_id(manifest_db)
    _mark_candidate_for_review(manifest_db, candidate_id)

    # When
    reassigned = _run_rpv(
        "constructs",
        "review",
        "reassign",
        candidate_id,
        "--construct",
        target_construct_id,
        "--config",
        str(config_path),
        "--actor",
        "tester",
        "--reason",
        "same construct family",
        cwd=tmp_path,
    )

    # Then
    assert reassigned.returncode == 0, reassigned.stderr
    assert f"construct review ok: action=reassign candidate_id={candidate_id}" in reassigned.stdout
    assert _candidate_target(manifest_db, candidate_id) == target_construct_id
    assert _candidate_review_state(manifest_db, candidate_id) == ("approved", 0)


def _config_text() -> str:
    return "\n".join(
        (
            'storage_roots = ["library"]',
            'cache_root = "cache"',
            'manifest_db = "cache/manifest.sqlite3"',
            'ocr_engine = "none"',
            'embedding_backend = "fixture"',
            'local_llm_backend = "disabled"',
            "enable_external_models = false",
            "max_external_passage_chars = 1200",
            "",
            "[sync]",
            'provider = "local"',
            "dry_run_metadata_only = false",
            "",
            "[approval]",
            'manual_review_lanes = ["red"]',
            "",
            "[notifications]",
            "discord_enabled = false",
            'discord_webhook_env = "RPV_DISCORD_WEBHOOK"',
            "",
            "[review_thresholds]",
            "green_min_confidence = 0.86",
            "amber_review_max_confidence = 0.70",
            "red_min_confidence = 0.95",
            "",
            "[privacy]",
            "allow_cloud_cache = false",
            "red_lane_metadata_only = true",
            "allow_external_pdf_upload = false",
            "",
        ),
    )


def _prepared_construct_vault(tmp_path: Path) -> Path:
    library = tmp_path / "library"
    library.mkdir()
    (library / "constructs.pdf").write_bytes(TEXT_PDF_BYTES)
    config_path = tmp_path / "rpv.toml"
    config_path.write_text(_config_text(), encoding="utf-8")
    ingest = _run_rpv("ingest", "--once", "--config", str(config_path), cwd=tmp_path)
    build = _run_rpv("constructs", "build", "--config", str(config_path), cwd=tmp_path)
    assert ingest.returncode == 0, ingest.stderr
    assert build.returncode == 0, build.stderr
    return config_path


def _run_rpv(
    *args: str,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RPV), *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def _first_candidate_id(manifest_db: Path) -> str:
    with sqlite3.connect(manifest_db) as connection:
        row = connection.execute(
            "SELECT candidate_id FROM construct_candidate ORDER BY reported_term LIMIT 1",
        ).fetchone()
    return str(row[0])


def _last_construct_id(manifest_db: Path) -> str:
    with sqlite3.connect(manifest_db) as connection:
        row = connection.execute(
            "SELECT construct_id FROM construct_registry ORDER BY canonical_label DESC LIMIT 1",
        ).fetchone()
    return str(row[0])


def _mark_candidate_for_review(manifest_db: Path, candidate_id: str) -> None:
    with sqlite3.connect(manifest_db) as connection:
        connection.execute(
            "UPDATE construct_candidate SET review_required = 1 WHERE candidate_id = ?",
            (candidate_id,),
        )


def _candidate_review_state(manifest_db: Path, candidate_id: str) -> tuple[str, int]:
    with sqlite3.connect(manifest_db) as connection:
        row = connection.execute(
            "SELECT candidate_status, review_required FROM construct_candidate WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
    return (str(row[0]), int(row[1]))


def _candidate_target(manifest_db: Path, candidate_id: str) -> str:
    with sqlite3.connect(manifest_db) as connection:
        row = connection.execute(
            "SELECT construct_id FROM construct_candidate WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
    return str(row[0])


def _candidate_rows(manifest_db: Path) -> list[tuple[str, str, str, str, int]]:
    with sqlite3.connect(manifest_db) as connection:
        rows = connection.execute(
            "SELECT reported_term, candidate_normalization, measurement_proxy, theoretical_role, review_required "
            "FROM construct_candidate ORDER BY reported_term",
        )
    return [(str(a), str(b), str(c), str(d), int(e)) for a, b, c, d, e in rows]
