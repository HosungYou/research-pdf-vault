from __future__ import annotations

import hashlib
from typing import Final

from research_pdf_vault.scan_db_models import ScannedFile

HASH_ID_LENGTH: Final = 24


def paper_id_from_result(item: ScannedFile) -> str:
    if item.result.sha256 is not None:
        return paper_id_from_sha(item.result.sha256)
    return f"paper_scan_{scan_trait_digest(item)}"


def paper_id_from_sha(sha256: str) -> str:
    return f"paper_sha_{sha256[:HASH_ID_LENGTH]}"


def instance_id_from_result(item: ScannedFile) -> str:
    if item.result.sha256 is not None:
        return instance_id_from_sha(item.result.sha256)
    return f"instance_scan_{scan_trait_digest(item)}"


def instance_id_from_sha(sha256: str) -> str:
    return f"instance_sha_{sha256[:HASH_ID_LENGTH]}"


def scan_trait_digest(item: ScannedFile) -> str:
    result = item.result
    return _digest_text(
        "\n".join(
            (
                result.status.value,
                str(result.size_bytes),
                str(result.mtime_ns),
                str(result.provider_status),
            ),
        ),
    )


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:HASH_ID_LENGTH]
