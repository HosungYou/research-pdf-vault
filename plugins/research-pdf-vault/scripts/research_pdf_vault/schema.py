from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import NewType, assert_never

SchemaVersion = NewType("SchemaVersion", str)
VaultId = NewType("VaultId", str)
PaperId = NewType("PaperId", str)
InstanceId = NewType("InstanceId", str)
DecisionId = NewType("DecisionId", str)
QueueItemId = NewType("QueueItemId", str)
AuditId = NewType("AuditId", str)
PassageId = NewType("PassageId", str)
ClaimId = NewType("ClaimId", str)
CitationSlotId = NewType("CitationSlotId", str)
ReportId = NewType("ReportId", str)
ArtifactId = NewType("ArtifactId", str)
RepoRelativePath = NewType("RepoRelativePath", str)
Sha256Hex = NewType("Sha256Hex", str)
ArtifactDigest = NewType("ArtifactDigest", str)
Timestamp = NewType("Timestamp", str)
Actor = NewType("Actor", str)


@unique
class Lane(StrEnum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


@unique
class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    QUARANTINED = "quarantined"


@unique
class InstanceStatus(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    PENDING_SYNC = "pending_sync"
    QUARANTINED = "quarantined"


@unique
class SupportTag(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    MIXED = "mixed"
    CONTEXT = "context"


@unique
class ArtifactKind(StrEnum):
    METADATA = "metadata"
    EXTRACTED_TEXT = "extracted_text"
    OCR_TEXT = "ocr_text"
    VECTOR_INDEX = "vector_index"
    CLAIM_CARDS = "claim_cards"
    CITATIONS = "citations"
    WORKER_REPORT = "worker_report"


@unique
class ReviewPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@unique
class AuditAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    CLASSIFY = "classify"
    QUARANTINE = "quarantine"
    RELEASE = "release"


def lane_can_carry_vector_path(lane: Lane) -> bool:
    match lane:
        case Lane.GREEN | Lane.AMBER:
            return True
        case Lane.RED:
            return False
        case unreachable:
            assert_never(unreachable)


def stage_can_carry_vector_path(stage_status: StageStatus) -> bool:
    match stage_status:
        case (
            StageStatus.PENDING
            | StageStatus.RUNNING
            | StageStatus.COMPLETE
            | StageStatus.FAILED
        ):
            return True
        case StageStatus.QUARANTINED:
            return False
        case unreachable:
            assert_never(unreachable)


def can_carry_vector_path(lane: Lane, stage_status: StageStatus) -> bool:
    return lane_can_carry_vector_path(lane) and stage_can_carry_vector_path(
        stage_status,
    )


@dataclass(frozen=True, slots=True)
class VectorArtifactPolicyError(Exception):
    artifact_id: ArtifactId
    lane: Lane
    stage_status: StageStatus

    def __str__(self) -> str:
        return (
            f"{self.artifact_id} cannot carry vector artifacts while "
            f"lane={self.lane.value} stage_status={self.stage_status.value}"
        )


@dataclass(frozen=True, slots=True)
class NormalizedIdentifiers:
    doi: str | None = None
    arxiv_id: str | None = None
    openalex_id: str | None = None


@dataclass(frozen=True, slots=True)
class SourceLocation:
    page: int
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class VaultConfig:
    schema_version: SchemaVersion
    vault_id: VaultId
    root_path: RepoRelativePath
    created_at: Timestamp
    default_lane: Lane


@dataclass(frozen=True, slots=True)
class Paper:
    schema_version: SchemaVersion
    paper_id: PaperId
    title: str
    normalized_identifiers: NormalizedIdentifiers
    lane: Lane
    created_at: Timestamp


@dataclass(frozen=True, slots=True)
class PaperInstance:
    schema_version: SchemaVersion
    instance_id: InstanceId
    paper_id: PaperId
    file_path: RepoRelativePath
    sha256: Sha256Hex | None
    instance_status: InstanceStatus
    discovered_at: Timestamp


@dataclass(frozen=True, slots=True)
class ClassificationDecision:
    schema_version: SchemaVersion
    decision_id: DecisionId
    paper_id: PaperId
    lane: Lane
    stage_status: StageStatus
    actor: Actor
    timestamp: Timestamp
    reason: str


@dataclass(frozen=True, slots=True)
class ReviewQueueItem:
    schema_version: SchemaVersion
    queue_item_id: QueueItemId
    paper_id: PaperId
    lane: Lane
    stage_status: StageStatus
    priority: ReviewPriority
    reason: str
    created_at: Timestamp


@dataclass(frozen=True, slots=True)
class AuditLog:
    schema_version: SchemaVersion
    audit_id: AuditId
    paper_id: PaperId
    actor: Actor
    timestamp: Timestamp
    action: AuditAction
    reason: str


@dataclass(frozen=True, slots=True)
class ExtractedPassage:
    schema_version: SchemaVersion
    passage_id: PassageId
    paper_id: PaperId
    instance_id: InstanceId
    source_location: SourceLocation
    text: str
    support_tag: SupportTag


@dataclass(frozen=True, slots=True)
class ClaimCard:
    schema_version: SchemaVersion
    claim_id: ClaimId
    paper_id: PaperId
    passage_id: PassageId
    claim_text: str
    support_tag: SupportTag
    source_location: SourceLocation


@dataclass(frozen=True, slots=True)
class CitationSlot:
    schema_version: SchemaVersion
    citation_slot_id: CitationSlotId
    paper_id: PaperId
    claim_id: ClaimId
    slot_label: str
    source_location: SourceLocation
    support_tag: SupportTag


@dataclass(frozen=True, slots=True)
class WorkerReport:
    schema_version: SchemaVersion
    report_id: ReportId
    worker_name: Actor
    paper_id: PaperId
    stage_status: StageStatus
    started_at: Timestamp
    finished_at: Timestamp
    artifact_digest: ArtifactDigest
    summary: str


@dataclass(frozen=True, slots=True)
class ArtifactStatus:
    schema_version: SchemaVersion
    artifact_id: ArtifactId
    paper_id: PaperId
    artifact_kind: ArtifactKind
    lane: Lane
    stage_status: StageStatus
    artifact_digest: ArtifactDigest
    created_at: Timestamp
    artifact_path: RepoRelativePath | None = None
    vector_artifact_path: RepoRelativePath | None = None

    def __post_init__(self) -> None:
        if self.vector_artifact_path is not None and not can_carry_vector_path(
            self.lane,
            self.stage_status,
        ):
            raise VectorArtifactPolicyError(
                artifact_id=self.artifact_id,
                lane=self.lane,
                stage_status=self.stage_status,
            )
