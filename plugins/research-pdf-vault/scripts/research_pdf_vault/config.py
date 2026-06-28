from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Final

from research_pdf_vault.config_defaults import SAMPLE_CONFIG_TEXT
from research_pdf_vault.config_models import (
    ApprovalSettings,
    ConfigLoadRequest,
    ConfigValidationError,
    NotificationSettings,
    PrivacySettings,
    ReviewThresholds,
    SyncSettings,
    VaultRuntimeConfig,
)
from research_pdf_vault.config_parse import (
    RawConfig,
    TomlConfigError,
    expand_path,
    optional_bool,
    optional_int,
    optional_path,
    optional_path_tuple,
    optional_section,
    optional_str,
    read_toml,
)
from research_pdf_vault.config_sections import (
    merge_approval,
    merge_notifications,
    merge_privacy,
    merge_sync,
    merge_thresholds,
)

ENV_CONFIG_PATH: Final = "RPV_CONFIG"
DEFAULT_CONFIG_NAME: Final = "rpv.toml"
MAX_EXTERNAL_PASSAGE_CHARS: Final = 4000


def default_config_path(working_dir: Path | None = None) -> Path:
    base_dir = working_dir if working_dir is not None else Path.cwd()
    return (base_dir / DEFAULT_CONFIG_NAME).resolve()


def resolve_config_path(request: ConfigLoadRequest) -> Path:
    environ = _environ(request)
    working_dir = _working_dir(request)
    if request.config_path is not None:
        return expand_path(request.config_path, working_dir)
    env_path = environ.get(ENV_CONFIG_PATH)
    if env_path:
        return expand_path(Path(env_path), working_dir)
    return default_config_path(working_dir)


def load_config(request: ConfigLoadRequest | None = None) -> VaultRuntimeConfig:
    load_request = request if request is not None else ConfigLoadRequest()
    environ = _environ(load_request)
    working_dir = _working_dir(load_request)
    selected_path = resolve_config_path(load_request)
    requested_path = load_request.config_path is not None or bool(
        environ.get(ENV_CONFIG_PATH),
    )
    config = _default_config(selected_path, environ)
    if not selected_path.exists():
        if requested_path:
            raise ConfigValidationError(f"config file not found: {selected_path}")
        return _validate_config(config)
    try:
        raw_config = read_toml(selected_path)
        merged = _merge_config(config, raw_config, selected_path.parent)
    except TomlConfigError as error:
        raise ConfigValidationError(str(error)) from error
    if not selected_path.is_absolute():
        return replace(merged, config_path=expand_path(selected_path, working_dir))
    return _validate_config(merged)


def write_default_config(config_path: Path, *, force: bool = False) -> Path:
    destination = config_path.expanduser().resolve()
    if destination.exists() and not force:
        raise ConfigValidationError(f"config already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(SAMPLE_CONFIG_TEXT, encoding="utf-8")
    return destination


def _environ(request: ConfigLoadRequest) -> Mapping[str, str]:
    return request.environ if request.environ is not None else os.environ


def _working_dir(request: ConfigLoadRequest) -> Path:
    return (request.working_dir if request.working_dir is not None else Path.cwd()).resolve()


def _default_config(config_path: Path, environ: Mapping[str, str]) -> VaultRuntimeConfig:
    cache_root = _default_cache_root(environ)
    return VaultRuntimeConfig(
        config_path=config_path.resolve(),
        storage_roots=(),
        cache_root=cache_root,
        manifest_db=cache_root / "manifest.sqlite3",
        ocr_engine="none",
        embedding_backend="fixture",
        local_llm_backend="disabled",
        enable_external_models=False,
        max_external_passage_chars=0,
        review_thresholds=ReviewThresholds(
            green_min_confidence=0.90,
            amber_review_max_confidence=0.70,
            red_min_confidence=0.95,
        ),
        privacy=PrivacySettings(
            allow_cloud_cache=False,
            red_lane_metadata_only=True,
            allow_external_pdf_upload=False,
        ),
        sync=SyncSettings(provider="local", dry_run_metadata_only=False),
        approval=ApprovalSettings(manual_review_lanes=("red",)),
        notifications=NotificationSettings(
            discord_enabled=False,
            discord_webhook_env="RPV_DISCORD_WEBHOOK",
        ),
    )


def _default_cache_root(environ: Mapping[str, str]) -> Path:
    xdg_cache = environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return (Path(xdg_cache).expanduser() / "research-pdf-vault").resolve()
    home = environ.get("HOME")
    if home:
        return (Path(home).expanduser() / ".cache" / "research-pdf-vault").resolve()
    return (Path.home() / ".cache" / "research-pdf-vault").resolve()


def _merge_config(
    defaults: VaultRuntimeConfig,
    raw_config: RawConfig,
    base_dir: Path,
) -> VaultRuntimeConfig:
    storage_roots = optional_path_tuple(raw_config, "storage_roots", base_dir)
    cache_root = optional_path(raw_config, "cache_root", base_dir)
    manifest_db = optional_path(raw_config, "manifest_db", base_dir)
    enable_external_models = optional_bool(raw_config, "enable_external_models")
    max_external_passage_chars = optional_int(
        raw_config,
        "max_external_passage_chars",
    )
    return _validate_config(
        replace(
            defaults,
            storage_roots=storage_roots
            if storage_roots is not None
            else defaults.storage_roots,
            cache_root=cache_root if cache_root is not None else defaults.cache_root,
            manifest_db=manifest_db if manifest_db is not None else defaults.manifest_db,
            ocr_engine=optional_str(raw_config, "ocr_engine") or defaults.ocr_engine,
            embedding_backend=optional_str(raw_config, "embedding_backend")
            or defaults.embedding_backend,
            local_llm_backend=optional_str(raw_config, "local_llm_backend")
            or defaults.local_llm_backend,
            enable_external_models=enable_external_models
            if enable_external_models is not None
            else defaults.enable_external_models,
            max_external_passage_chars=max_external_passage_chars
            if max_external_passage_chars is not None
            else defaults.max_external_passage_chars,
            review_thresholds=merge_thresholds(
                defaults.review_thresholds,
                optional_section(raw_config, "review_thresholds"),
            ),
            privacy=merge_privacy(
                defaults.privacy,
                optional_section(raw_config, "privacy"),
            ),
            sync=merge_sync(defaults.sync, optional_section(raw_config, "sync")),
            approval=merge_approval(
                defaults.approval,
                optional_section(raw_config, "approval"),
            ),
            notifications=merge_notifications(
                defaults.notifications,
                optional_section(raw_config, "notifications"),
            ),
        ),
    )


def _validate_config(config: VaultRuntimeConfig) -> VaultRuntimeConfig:
    _validate_external_policy(config)
    _validate_cloud_policy(config.cache_root, config.privacy)
    _validate_cloud_policy(config.manifest_db, config.privacy)
    return config


def _validate_external_policy(config: VaultRuntimeConfig) -> None:
    max_chars = config.max_external_passage_chars
    if max_chars < 0 or max_chars > MAX_EXTERNAL_PASSAGE_CHARS:
        raise ConfigValidationError(
            f"max_external_passage_chars must be 0..{MAX_EXTERNAL_PASSAGE_CHARS}",
        )
    if config.enable_external_models and max_chars <= 0:
        raise ConfigValidationError(
            "max_external_passage_chars must be greater than 0 when external models are enabled",
        )


def _validate_cloud_policy(path: Path, privacy: PrivacySettings) -> None:
    if "CloudStorage" in path.parts and not privacy.allow_cloud_cache:
        raise ConfigValidationError(
            f"cache paths under CloudStorage require allow_cloud_cache = true: {path}",
        )
