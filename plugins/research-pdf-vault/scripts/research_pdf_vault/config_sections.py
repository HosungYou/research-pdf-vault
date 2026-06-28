from __future__ import annotations

from typing import Final

from research_pdf_vault.config_models import (
    ApprovalSettings,
    ConfigValidationError,
    NotificationSettings,
    PrivacySettings,
    ReviewThresholds,
    SyncSettings,
)
from research_pdf_vault.config_parse import (
    RawConfig,
    optional_bool,
    optional_float,
    optional_str,
    optional_str_tuple,
)

MANUAL_REVIEW_LANES: Final = frozenset(("amber", "red"))


def merge_thresholds(
    defaults: ReviewThresholds,
    raw_section: RawConfig | None,
) -> ReviewThresholds:
    if raw_section is None:
        return defaults
    green_min_confidence = optional_float(raw_section, "green_min_confidence")
    amber_review_max_confidence = optional_float(
        raw_section,
        "amber_review_max_confidence",
    )
    red_min_confidence = optional_float(raw_section, "red_min_confidence")
    thresholds = ReviewThresholds(
        green_min_confidence=green_min_confidence
        if green_min_confidence is not None
        else defaults.green_min_confidence,
        amber_review_max_confidence=amber_review_max_confidence
        if amber_review_max_confidence is not None
        else defaults.amber_review_max_confidence,
        red_min_confidence=red_min_confidence
        if red_min_confidence is not None
        else defaults.red_min_confidence,
    )
    for value in (
        thresholds.green_min_confidence,
        thresholds.amber_review_max_confidence,
        thresholds.red_min_confidence,
    ):
        if value < 0.0 or value > 1.0:
            raise ConfigValidationError("review thresholds must be between 0 and 1")
    return thresholds


def merge_privacy(
    defaults: PrivacySettings,
    raw_section: RawConfig | None,
) -> PrivacySettings:
    if raw_section is None:
        return defaults
    allow_cloud_cache = optional_bool(raw_section, "allow_cloud_cache")
    red_lane_metadata_only = optional_bool(raw_section, "red_lane_metadata_only")
    allow_external_pdf_upload = optional_bool(raw_section, "allow_external_pdf_upload")
    return PrivacySettings(
        allow_cloud_cache=allow_cloud_cache
        if allow_cloud_cache is not None
        else defaults.allow_cloud_cache,
        red_lane_metadata_only=red_lane_metadata_only
        if red_lane_metadata_only is not None
        else defaults.red_lane_metadata_only,
        allow_external_pdf_upload=allow_external_pdf_upload
        if allow_external_pdf_upload is not None
        else defaults.allow_external_pdf_upload,
    )


def merge_sync(defaults: SyncSettings, raw_section: RawConfig | None) -> SyncSettings:
    if raw_section is None:
        return defaults
    dry_run_metadata_only = optional_bool(raw_section, "dry_run_metadata_only")
    return SyncSettings(
        provider=optional_str(raw_section, "provider") or defaults.provider,
        dry_run_metadata_only=dry_run_metadata_only
        if dry_run_metadata_only is not None
        else defaults.dry_run_metadata_only,
    )


def merge_approval(
    defaults: ApprovalSettings,
    raw_section: RawConfig | None,
) -> ApprovalSettings:
    if raw_section is None:
        return defaults
    lanes = optional_str_tuple(raw_section, "manual_review_lanes")
    if lanes is None:
        return defaults
    normalized = tuple(lane.casefold() for lane in lanes)
    unexpected = tuple(lane for lane in normalized if lane not in MANUAL_REVIEW_LANES)
    if unexpected:
        raise ConfigValidationError(
            f"manual_review_lanes may include only amber/red: {', '.join(unexpected)}",
        )
    return ApprovalSettings(manual_review_lanes=normalized)


def merge_notifications(
    defaults: NotificationSettings,
    raw_section: RawConfig | None,
) -> NotificationSettings:
    if raw_section is None:
        return defaults
    discord_enabled = optional_bool(raw_section, "discord_enabled")
    return NotificationSettings(
        discord_enabled=discord_enabled
        if discord_enabled is not None
        else defaults.discord_enabled,
        discord_webhook_env=optional_str(raw_section, "discord_webhook_env")
        or defaults.discord_webhook_env,
    )
