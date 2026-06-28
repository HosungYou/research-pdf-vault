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
SAMPLE_CONFIG: Final = ROOT / "fixtures" / "config" / "sample-config.toml"
SAMPLE_DB: Final = ROOT / "fixtures" / "config" / "cache" / "research-pdf-vault" / "manifest.sqlite3"


def test_sample_config_ingest_when_run_once_then_demonstrates_all_lanes() -> None:
    # Given
    if SAMPLE_DB.exists():
        SAMPLE_DB.unlink()

    # When
    ingest = _run_rpv("ingest", "--config", str(SAMPLE_CONFIG), "--once")
    report = _run_rpv("report", "--config", str(SAMPLE_CONFIG))
    review = _run_rpv("review", "list", "--config", str(SAMPLE_CONFIG))

    # Then
    assert ingest.returncode == 0, ingest.stderr
    assert "indexed=1" in ingest.stdout
    assert "chunks=2" in ingest.stdout
    assert "vectors=2" in ingest.stdout
    assert "quarantined=1" in ingest.stdout
    assert "skipped=2" in ingest.stdout

    assert report.returncode == 0, report.stderr
    payload = json.loads(report.stdout)
    assert payload["lanes"]["green"] >= 1
    assert payload["lanes"]["amber"] >= 1
    assert payload["lanes"]["red"] >= 1
    assert payload["review_queue"].get("pending", 0) == 0
    assert payload["review_queue"]["quarantined"] >= 1

    assert review.returncode == 0, review.stderr
    assert "red" in review.stdout
    assert "amber" not in review.stdout
    assert _red_index_row_count() == 0


def _run_rpv(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RPV), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _red_index_row_count() -> int:
    with sqlite3.connect(SAMPLE_DB) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM paper p "
            "JOIN index_chunk c ON c.paper_id = p.paper_id "
            "JOIN chunk_embedding e ON e.chunk_id = c.chunk_id "
            "WHERE p.lane = 'red'",
        ).fetchone()
    return int(row[0])
