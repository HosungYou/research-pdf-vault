---
name: research-vault-automation
description: Compose Codex automation prompts for Research PDF Vault digests and alerts that read generated reports or triage outputs and notify humans without running background vault workers.
---

# Research Vault Automation

## When To Use

Use this skill when the user wants scheduled or event-style Codex automation prompts for Research PDF Vault. Automations should read generated reports, review queue triage, and citation-slot readiness output, then produce a notification or summary.

## Safety Boundary

Codex automations are report readers and notification writers. They avoid direct OCR, direct PDF vectorization, and persistent worker service launch. If fresh processing is needed, tell the user which one-shot CLI command should be run outside the automation prompt.

## Prompt Templates

Use the templates under `plugins/research-pdf-vault/assets/automation-prompts/`:

- `daily-digest.md`
- `review-queue-alert.md`
- `ingestion-failure-alert.md`
- `citation-slot-readiness.md`

## Inputs

Use one or more of these generated inputs:

- CLI output from `rpv.py setup --check`, `rpv.py scan --once`, or `rpv.py ingest --once`.
- Review queue output from `rpv.py review list` and `rpv.py review show`.
- Discord dry-run payloads from `rpv.py notify discord --event review-queue --dry-run`.
- MCP output from `list_review_queue` and `apply_review_decision` when available.
- Worker report summaries from local report tools such as `list_reports` and `get_report`.
- Citation output from `rpv.py citation-slots build`.
- Literature-map output from `rpv.py literature-map report`.

## Automation Pattern

1. Read the latest generated report, queue, or citation-slot artifact supplied by the user or scheduler.
2. Extract counts, status changes, failures, and next actions.
3. Write a short notification with no private file paths or real PDF names.
4. Include the exact one-shot CLI command a human can run when fresh processing is required.
5. Prefer Red-lane decision alerts over Amber alerts unless the config explicitly lists Amber in `manual_review_lanes`.

## Notification Rules

- Keep examples public-safe and synthetic.
- Never include secrets, personal paths, institutional strings, or real document titles.
- Prefer IDs, counts, status labels, and short remediation steps.
- Discord messages should contain counts and commands only, not document titles or source paths.
- Do not imply that an automation prompt is a persistent service.
