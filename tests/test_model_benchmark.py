from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
RPV: Final = SCRIPTS_DIR / "rpv.py"


def test_model_benchmark_profiles_when_listed_then_qwen_is_default_and_glm_is_opt_in() -> None:
    # Given / When
    completed = subprocess.run(
        [sys.executable, str(RPV), "model-benchmark", "profiles"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["default_profile"] == "qwen-local-default"
    profiles = {profile["profile_id"]: profile for profile in payload["profiles"]}
    assert profiles["qwen-local-default"]["model_family"] == "qwen"
    assert profiles["glm-4.5-air-experimental"]["model_family"] == "glm"
    assert profiles["glm-4.5-air-experimental"]["requires_explicit_opt_in"] is True


def test_model_benchmark_run_dry_run_when_glm_without_opt_in_then_refuses_heavy_profile() -> None:
    # Given / When
    completed = subprocess.run(
        [
            sys.executable,
            str(RPV),
            "model-benchmark",
            "run",
            "--profile",
            "glm-4.5-air-experimental",
            "--dry-run",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert completed.returncode == 1
    assert "requires --allow-heavy" in completed.stderr


def test_model_benchmark_run_dry_run_when_qwen_default_then_reports_privacy_guardrails() -> None:
    # Given / When
    completed = subprocess.run(
        [
            sys.executable,
            str(RPV),
            "model-benchmark",
            "run",
            "--profile",
            "qwen-local-default",
            "--dry-run",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "dry_run"
    assert payload["profile_id"] == "qwen-local-default"
    assert payload["privacy"]["red_lane_body_allowed"] is False
    assert payload["metrics_to_capture"] == [
        "classification_accuracy",
        "literature_map_edge_precision",
        "tokens_per_second",
        "peak_memory_gb",
        "failure_rate",
    ]
