# Research PDF Vault Daily Digest Prompt

## Purpose

Create a daily digest from generated Research PDF Vault reports, review queue output, and citation-slot readiness summaries.

## Inputs

- Latest setup, scan, ingest, and report summaries supplied to the automation.
- Optional review queue listing from `rpv.py review list` or MCP `list_review_queue`.
- Optional citation-slot JSON from `rpv.py citation-slots build`.
- Optional literature-map JSON from `rpv.py literature-map report`.
- Optional Discord dry-run payload from `rpv.py notify discord --event review-queue --dry-run`.

## Boundary

This automation reads generated reports and triage output only. It avoids direct OCR, direct PDF vectorization, and persistent worker service launch.

## Instructions

1. Summarize ingest health: scanned, ready, pending, indexed, quarantined, skipped, and failed counts.
2. Summarize review queue pressure by lane, priority, and reason.
3. Summarize citation-slot readiness by project and support tag.
4. Summarize literature-map node and edge counts when available.
5. List at most five human actions, ordered by urgency.
6. If fresh processing is required, mention the relevant one-shot command, such as:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py ingest --once --config fixtures/config/sample-config.toml
```

## Output Format

- `Status`
- `Ingestion`
- `Review Queue`
- `Citation Slots`
- `Literature Map`
- `Actions`

Use synthetic IDs only. Do not include personal paths, institutional strings, real PDF names, or secrets.
