from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Final, assert_never

from research_pdf_vault.classification import FirstPassClassification, classify_document
from research_pdf_vault.config import VaultRuntimeConfig
from research_pdf_vault.db import SCHEMA_VERSION
from research_pdf_vault.document_traits import (
    DocumentClassificationInput,
    DocumentMetadata,
    DocumentTraits,
    DocumentTypeHint,
)
from research_pdf_vault.review_policy import priority_for_lane, queue_item_id
from research_pdf_vault.schema import Lane
from research_pdf_vault.scan_db import HASH_ID_LENGTH, ScanBatch, ScannedFile
from research_pdf_vault.synthetic_pdf import synthetic_text_pages

CLASSIFIER_ACTOR: Final = "sample-scan-classifier"


@dataclass(frozen=True, slots=True)
class ScanClassificationRecord:
    paper_id: str
    title: str
    identifiers_json: str
    decision: FirstPassClassification
    observed_at: str


def record_ready_classification(
    connection: sqlite3.Connection,
    batch: ScanBatch,
    item: ScannedFile,
    config: VaultRuntimeConfig,
) -> None:
    sha256 = item.result.sha256
    if sha256 is None:
        return
    document = _classification_input(item)
    decision = classify_document(document)
    record = ScanClassificationRecord(
        paper_id=f"paper_sha_{sha256[:HASH_ID_LENGTH]}",
        title=document.metadata.title,
        identifiers_json=_identifiers_json(item, document, decision),
        decision=decision,
        observed_at=batch.observed_at,
    )
    _update_paper(connection, record)
    _upsert_decision(connection, record)
    _sync_review_item(connection, record, config)


def _classification_input(item: ScannedFile) -> DocumentClassificationInput:
    excerpt = _light_text_excerpt(item.source_path)
    return DocumentClassificationInput(
        path=Path(item.relative_path),
        metadata=_metadata_for_path(item.relative_path, excerpt),
        traits=DocumentTraits(),
        light_text_excerpt=excerpt,
    )


def _metadata_for_path(relative_path: str, excerpt: str | None) -> DocumentMetadata:
    path_text = Path(relative_path).as_posix().casefold()
    combined_text = " ".join((path_text, excerpt.casefold() if excerpt else ""))
    return DocumentMetadata(
        title=_title_from_path(relative_path),
        document_type_hint=_type_hint(combined_text),
        keywords=tuple(combined_text.replace("-", " ").replace("_", " ").split()),
    )


def _type_hint(path_text: str) -> DocumentTypeHint:
    if "presentation" in path_text or "deck" in path_text:
        return DocumentTypeHint.PRESENTATION
    if "official" in path_text or "report" in path_text:
        return DocumentTypeHint.OFFICIAL_REPORT
    if "research" in path_text or "article" in path_text:
        return DocumentTypeHint.RESEARCH_ARTICLE
    return DocumentTypeHint.UNKNOWN


def _title_from_path(relative_path: str) -> str:
    stem = Path(relative_path).stem.replace("-", " ").replace("_", " ").strip()
    if stem:
        return stem.title()
    return "Untitled scanned paper"


def _light_text_excerpt(source_path: Path) -> str | None:
    pages = synthetic_text_pages(source_path.read_bytes())
    if not pages:
        return None
    return "\n".join(page.text for page in pages)[:1200]


def _identifiers_json(
    item: ScannedFile,
    document: DocumentClassificationInput,
    decision: FirstPassClassification,
) -> str:
    return json.dumps(
        {
            "classification_reasons": decision.reason_codes,
            "document_type_hint": document.metadata.document_type_hint.value,
            "source": "scan",
            "source_path": item.relative_path,
        },
        sort_keys=True,
    )


def _update_paper(
    connection: sqlite3.Connection,
    record: ScanClassificationRecord,
) -> None:
    connection.execute(
        "UPDATE paper SET title = ?, normalized_identifiers = ?, lane = ? "
        "WHERE paper_id = ?",
        (
            record.title,
            record.identifiers_json,
            record.decision.lane.value,
            record.paper_id,
        ),
    )


def _upsert_decision(
    connection: sqlite3.Connection,
    record: ScanClassificationRecord,
) -> None:
    connection.execute(
        "INSERT INTO classification_decision "
        "(schema_version, decision_id, paper_id, lane, stage_status, actor, timestamp, reason) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(decision_id) DO UPDATE SET "
        "lane = excluded.lane, stage_status = excluded.stage_status, "
        "timestamp = excluded.timestamp, reason = excluded.reason",
        (
            SCHEMA_VERSION,
            f"decision_scan_{record.paper_id.removeprefix('paper_')}",
            record.paper_id,
            record.decision.lane.value,
            record.decision.stage_status.value,
            CLASSIFIER_ACTOR,
            record.observed_at,
            ", ".join(record.decision.reasons),
        ),
    )


def _sync_review_item(
    connection: sqlite3.Connection,
    record: ScanClassificationRecord,
    config: VaultRuntimeConfig,
) -> None:
    lane = record.decision.lane
    if not _manual_review_required(config, lane):
        connection.execute(
            "DELETE FROM review_queue_item WHERE paper_id = ?",
            (record.paper_id,),
        )
        return
    connection.execute(
        "INSERT INTO review_queue_item "
        "(schema_version, queue_item_id, paper_id, lane, stage_status, priority, reason, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(queue_item_id) DO UPDATE SET "
        "lane = excluded.lane, stage_status = excluded.stage_status, "
        "priority = excluded.priority, reason = excluded.reason",
        (
            SCHEMA_VERSION,
            queue_item_id(record.paper_id),
            record.paper_id,
            lane.value,
            record.decision.stage_status.value,
            priority_for_lane(lane).value,
            ", ".join(record.decision.reasons),
            record.observed_at,
        ),
    )


def _manual_review_required(config: VaultRuntimeConfig, lane: Lane) -> bool:
    match lane:
        case Lane.RED | Lane.AMBER:
            return lane.value in config.approval.manual_review_lanes
        case Lane.GREEN:
            return False
        case unreachable:
            assert_never(unreachable)
