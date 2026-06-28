from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS_DIR: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts"
CONFIG_FIXTURES: Final = ROOT / "fixtures" / "config"
SAMPLE_CONFIG: Final = CONFIG_FIXTURES / "sample-config.toml"
RPV_SCRIPT: Final = SCRIPTS_DIR / "rpv.py"
sys.path.insert(0, str(SCRIPTS_DIR))


def config_text(cache_name: str, root_name: str = "root") -> str:
    return "\n".join(
        (
            f'storage_roots = ["{root_name}"]',
            f'cache_root = "{cache_name}"',
            f'manifest_db = "{cache_name}/manifest.sqlite3"',
            'ocr_engine = "none"',
            'embedding_backend = "fixture"',
            'local_llm_backend = "disabled"',
            "enable_external_models = false",
            "max_external_passage_chars = 1200",
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


def write_config(path: Path, cache_name: str) -> None:
    path.write_text(config_text(cache_name), encoding="utf-8")


def test_sample_config_validates_and_expands_fixture_paths() -> None:
    from research_pdf_vault.config import ConfigLoadRequest, load_config

    # Given
    expected_cache = CONFIG_FIXTURES / "cache" / "research-pdf-vault"

    # When
    config = load_config(ConfigLoadRequest(config_path=SAMPLE_CONFIG))

    # Then
    assert config.cache_root == expected_cache.resolve()
    assert config.manifest_db == (expected_cache / "manifest.sqlite3").resolve()
    assert config.storage_roots == (
        (CONFIG_FIXTURES / "storage-roots" / "synthetic-library").resolve(),
    )
    assert config.enable_external_models is False


def test_cloud_cache_policy_rejects_simulated_cloudstorage_without_override() -> None:
    from research_pdf_vault.config import (
        ConfigLoadRequest,
        ConfigValidationError,
        load_config,
    )

    # Given
    blocked_config = CONFIG_FIXTURES / "failure" / "cloud-cache.toml"
    allowed_config = CONFIG_FIXTURES / "failure" / "cloud-cache-allowed.toml"

    # When / Then
    with pytest.raises(ConfigValidationError, match="CloudStorage"):
        load_config(ConfigLoadRequest(config_path=blocked_config))

    allowed = load_config(ConfigLoadRequest(config_path=allowed_config))
    assert "CloudStorage" in allowed.cache_root.parts


def test_config_path_precedence_prefers_cli_then_environment_then_default(
    tmp_path: Path,
) -> None:
    from research_pdf_vault.config import ConfigLoadRequest, load_config

    # Given
    default_config = tmp_path / "rpv.toml"
    env_config = tmp_path / "env.toml"
    cli_config = tmp_path / "cli.toml"
    write_config(default_config, "default-cache")
    write_config(env_config, "env-cache")
    write_config(cli_config, "cli-cache")
    env = {"RPV_CONFIG": str(env_config), "HOME": str(tmp_path / "home")}

    # When
    cli_selected = load_config(
        ConfigLoadRequest(
            config_path=cli_config,
            environ=env,
            working_dir=tmp_path,
        ),
    )
    env_selected = load_config(
        ConfigLoadRequest(config_path=None, environ=env, working_dir=tmp_path),
    )
    default_selected = load_config(
        ConfigLoadRequest(
            config_path=None,
            environ={"HOME": str(tmp_path / "home")},
            working_dir=tmp_path,
        ),
    )

    # Then
    assert cli_selected.config_path == cli_config.resolve()
    assert cli_selected.cache_root == (tmp_path / "cli-cache").resolve()
    assert env_selected.config_path == env_config.resolve()
    assert env_selected.cache_root == (tmp_path / "env-cache").resolve()
    assert default_selected.config_path == default_config.resolve()
    assert default_selected.cache_root == (tmp_path / "default-cache").resolve()


def test_review_thresholds_preserve_explicit_zero_values(tmp_path: Path) -> None:
    from research_pdf_vault.config import ConfigLoadRequest, load_config

    # Given
    config_path = tmp_path / "zero-thresholds.toml"
    config_path.write_text(
        config_text("zero-cache")
        .replace("green_min_confidence = 0.86", "green_min_confidence = 0.0")
        .replace(
            "amber_review_max_confidence = 0.70",
            "amber_review_max_confidence = 0.0",
        )
        .replace("red_min_confidence = 0.95", "red_min_confidence = 0.0"),
        encoding="utf-8",
    )

    # When
    config = load_config(
        ConfigLoadRequest(config_path=config_path, working_dir=tmp_path),
    )

    # Then
    assert config.review_thresholds.green_min_confidence == 0.0
    assert config.review_thresholds.amber_review_max_confidence == 0.0
    assert config.review_thresholds.red_min_confidence == 0.0


def test_setup_init_writes_config_and_refuses_to_overwrite_without_force(
    tmp_path: Path,
) -> None:
    # Given
    config_path = tmp_path / "generated.toml"
    command = [
        sys.executable,
        str(RPV_SCRIPT),
        "setup",
        "--init",
        "--config",
        str(config_path),
    ]

    # When
    first = subprocess.run(command, check=False, text=True, capture_output=True)
    second = subprocess.run(command, check=False, text=True, capture_output=True)
    forced = subprocess.run(
        [*command, "--force"],
        check=False,
        text=True,
        capture_output=True,
    )

    # Then
    assert first.returncode == 0, first.stderr
    assert config_path.exists()
    assert second.returncode != 0
    assert "already exists" in second.stderr
    assert forced.returncode == 0, forced.stderr


def test_setup_check_uses_cli_config_before_environment_config(
    tmp_path: Path,
) -> None:
    # Given
    valid_config = tmp_path / "valid.toml"
    invalid_env_config = tmp_path / "invalid-env.toml"
    write_config(valid_config, "valid-cache")
    invalid_env_config.write_text(
        config_text("CloudStorage/simulated-cache"),
        encoding="utf-8",
    )
    env = os.environ | {"RPV_CONFIG": str(invalid_env_config)}

    # When
    result = subprocess.run(
        [
            sys.executable,
            str(RPV_SCRIPT),
            "setup",
            "--check",
            "--config",
            str(valid_config),
        ],
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )

    # Then
    assert result.returncode == 0, result.stderr
    assert str(valid_config.resolve()) in result.stdout
