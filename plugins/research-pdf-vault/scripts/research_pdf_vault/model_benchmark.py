from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from research_pdf_vault.mcp_types import JsonObject

BENCHMARK_METRICS: Final[tuple[str, ...]] = (
    "classification_accuracy",
    "literature_map_edge_precision",
    "tokens_per_second",
    "peak_memory_gb",
    "failure_rate",
)


@dataclass(frozen=True, slots=True)
class ModelProfile:
    profile_id: str
    model_family: str
    display_name: str
    recommended_role: str
    estimated_min_memory_gb: int
    requires_explicit_opt_in: bool

    def to_json(self) -> JsonObject:
        return {
            "profile_id": self.profile_id,
            "model_family": self.model_family,
            "display_name": self.display_name,
            "recommended_role": self.recommended_role,
            "estimated_min_memory_gb": self.estimated_min_memory_gb,
            "requires_explicit_opt_in": self.requires_explicit_opt_in,
        }


@dataclass(frozen=True, slots=True)
class ModelBenchmarkRefused(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


MODEL_PROFILES: Final[tuple[ModelProfile, ...]] = (
    ModelProfile(
        profile_id="qwen-local-default",
        model_family="qwen",
        display_name="Qwen local default",
        recommended_role="literature map classification and graph extraction",
        estimated_min_memory_gb=32,
        requires_explicit_opt_in=False,
    ),
    ModelProfile(
        profile_id="qwen-small-fast",
        model_family="qwen",
        display_name="Qwen small fast",
        recommended_role="fast metadata triage",
        estimated_min_memory_gb=16,
        requires_explicit_opt_in=False,
    ),
    ModelProfile(
        profile_id="glm-4.5-air-experimental",
        model_family="glm",
        display_name="GLM-4.5-Air experimental",
        recommended_role="high-quality local experiment on short contexts",
        estimated_min_memory_gb=64,
        requires_explicit_opt_in=True,
    ),
)
DEFAULT_PROFILE_ID: Final = "qwen-local-default"


def profiles_payload() -> JsonObject:
    return {
        "default_profile": DEFAULT_PROFILE_ID,
        "profiles": [profile.to_json() for profile in MODEL_PROFILES],
    }


def benchmark_dry_run(profile_id: str, *, allow_heavy: bool) -> JsonObject:
    profile = profile_by_id(profile_id)
    if profile.requires_explicit_opt_in and not allow_heavy:
        raise ModelBenchmarkRefused(f"{profile.profile_id} requires --allow-heavy")
    return {
        "status": "dry_run",
        "profile_id": profile.profile_id,
        "model_family": profile.model_family,
        "metrics_to_capture": list(BENCHMARK_METRICS),
        "privacy": {
            "red_lane_body_allowed": False,
            "external_pdf_upload_allowed": False,
        },
    }


def profile_by_id(profile_id: str) -> ModelProfile:
    for profile in MODEL_PROFILES:
        if profile.profile_id == profile_id:
            return profile
    raise ModelBenchmarkRefused(f"unknown model benchmark profile: {profile_id}")
