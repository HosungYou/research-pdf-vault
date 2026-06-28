from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ConfigValidationError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class ConfigLoadRequest:
    config_path: Path | None = None
    environ: Mapping[str, str] | None = None
    working_dir: Path | None = None


@dataclass(frozen=True, slots=True)
class ReviewThresholds:
    green_min_confidence: float
    amber_review_max_confidence: float
    red_min_confidence: float


@dataclass(frozen=True, slots=True)
class PrivacySettings:
    allow_cloud_cache: bool
    red_lane_metadata_only: bool
    allow_external_pdf_upload: bool


@dataclass(frozen=True, slots=True)
class SyncSettings:
    provider: str
    dry_run_metadata_only: bool


@dataclass(frozen=True, slots=True)
class ApprovalSettings:
    manual_review_lanes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NotificationSettings:
    discord_enabled: bool
    discord_webhook_env: str


@dataclass(frozen=True, slots=True)
class VaultRuntimeConfig:
    config_path: Path
    storage_roots: tuple[Path, ...]
    cache_root: Path
    manifest_db: Path
    ocr_engine: str
    embedding_backend: str
    local_llm_backend: str
    enable_external_models: bool
    max_external_passage_chars: int
    review_thresholds: ReviewThresholds
    privacy: PrivacySettings
    sync: SyncSettings
    approval: ApprovalSettings
    notifications: NotificationSettings
