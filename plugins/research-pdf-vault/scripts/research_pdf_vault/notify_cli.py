from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Protocol, assert_never

from research_pdf_vault.config import ConfigLoadRequest, load_config
from research_pdf_vault.mcp_manifest import get_manifest_summary
from research_pdf_vault.notifications import (
    DiscordNotificationError,
    NotificationEvent,
    build_discord_payload,
    send_discord_payload,
)


class SubparserCollection(Protocol):
    def add_parser(self, name: str) -> argparse.ArgumentParser: ...


def add_notify_parser(subparsers: SubparserCollection) -> None:
    notify_parser = subparsers.add_parser("notify")
    notify_subparsers = notify_parser.add_subparsers(
        dest="notify_command",
        required=True,
    )
    discord_parser = notify_subparsers.add_parser("discord")
    discord_parser.add_argument("--config", type=Path)
    discord_parser.add_argument(
        "--event",
        required=True,
        choices=tuple(event.value for event in NotificationEvent),
    )
    mode = discord_parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--send", action="store_true")


def run_notify(args: argparse.Namespace) -> int:
    match args.notify_command:
        case "discord":
            return _run_discord(args)
        case _ as unreachable:
            assert_never(unreachable)


def _run_discord(args: argparse.Namespace) -> int:
    config = load_config(ConfigLoadRequest(config_path=args.config))
    payload = build_discord_payload(
        get_manifest_summary(config),
        NotificationEvent(args.event),
    )
    if args.dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if not config.notifications.discord_enabled:
        print("error: discord notifications are disabled in config", file=sys.stderr)
        return 1
    webhook_url = os.environ.get(config.notifications.discord_webhook_env)
    if not webhook_url:
        print(
            f"error: missing Discord webhook env {config.notifications.discord_webhook_env}",
            file=sys.stderr,
        )
        return 1
    try:
        send_discord_payload(webhook_url, payload)
    except DiscordNotificationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print("discord notification sent")
    return 0
