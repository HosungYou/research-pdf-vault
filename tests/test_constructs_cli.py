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


def _candidate_rows(manifest_db: Path) -> list[tuple[str, str, str, str, int]]:
    with sqlite3.connect(manifest_db) as connection:
        rows = connection.execute(
            "SELECT reported_term, candidate_normalization, measurement_proxy, theoretical_role, review_required "
            "FROM construct_candidate ORDER BY reported_term",
        )
    return [(str(a), str(b), str(c), str(d), int(e)) for a, b, c, d, e in rows]
