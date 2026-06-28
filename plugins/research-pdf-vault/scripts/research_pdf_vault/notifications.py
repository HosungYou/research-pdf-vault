from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import StrEnum, unique
from typing import assert_never

from research_pdf_vault.mcp_types import JsonObject, is_json_object


@unique
class NotificationEvent(StrEnum):
    REVIEW_QUEUE = "review-queue"
    DAILY_DIGEST = "daily-digest"
    INGEST_COMPLETE = "ingest-complete"


@dataclass(frozen=True, slots=True)
class DiscordNotificationError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def build_discord_payload(summary: JsonObject, event: NotificationEvent) -> JsonObject:
    red_review_count = _count(summary, "review_queue", "quarantined")
    pending_review_count = _count(summary, "review_queue", "pending")
    paper_count = _count(summary, "counts", "papers")
    instance_count = _count(summary, "counts", "instances")
    match event:
        case NotificationEvent.REVIEW_QUEUE:
            content = f"Research PDF Vault: Red review needed: {red_review_count}"
            title = "Red review queue"
        case NotificationEvent.DAILY_DIGEST:
            content = (
                "Research PDF Vault daily digest: "
                f"{paper_count} papers, Red review needed: {red_review_count}"
            )
            title = "Daily digest"
        case NotificationEvent.INGEST_COMPLETE:
            content = (
                "Research PDF Vault ingest complete: "
                f"{instance_count} instances, pending review: {pending_review_count}"
            )
            title = "Ingest complete"
        case unreachable:
            assert_never(unreachable)
    return {
        "username": "Research PDF Vault",
        "content": content,
        "embeds": [
            {
                "title": title,
                "description": "\n".join(
                    (
                        f"Red review needed: {red_review_count}",
                        f"Pending review: {pending_review_count}",
                        "Run: rpv review list --config <your-config>",
                    ),
                ),
                "color": 15158332 if red_review_count else 3066993,
            },
        ],
    }


def send_discord_payload(webhook_url: str, payload: JsonObject) -> None:
    encoded = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=encoded,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "research-pdf-vault",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = response.status
    except urllib.error.HTTPError as error:
        raise DiscordNotificationError(
            f"discord webhook returned HTTP {error.code}",
        ) from error
    except urllib.error.URLError as error:
        raise DiscordNotificationError(f"discord webhook failed: {error.reason}") from error
    if status < 200 or status >= 300:
        raise DiscordNotificationError(f"discord webhook returned HTTP {status}")


def _count(summary: JsonObject, section: str, key: str) -> int:
    section_value = summary.get(section)
    if not is_json_object(section_value):
        return 0
    value = section_value.get(key)
    if type(value) is int:
        return value
    return 0
