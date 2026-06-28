# Research PDF Vault Ingestion Failure Alert Prompt

## Purpose

Notify a human when generated setup, scan, ingest, or report summaries show ingestion failures.

## Inputs

- `rpv.py setup --check` output.
- `rpv.py scan --once` output.
- `rpv.py ingest --once` output.
- Optional worker report summaries from local report tools.

## Boundary

This automation reads generated reports and triage output only. It avoids direct OCR, direct PDF vectorization, and persistent worker service launch.

## Instructions

1. Classify the failure as configuration, scan, indexing, quarantine, or report-read failure.
2. Extract counts and IDs from generated summaries only.
3. Give one concise remediation step per failure class.
4. Include a setup check command when configuration may be stale:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py setup --check --config fixtures/config/sample-config.toml
```

5. Include the one-shot ingest command when reprocessing should be triggered by a human:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py ingest --once --config fixtures/config/sample-config.toml
```

## Output Format

- `Failure`
- `Observed Counts`
- `Likely Cause`
- `Human Action`

Use synthetic IDs only. Do not include personal paths, institutional strings, real PDF names, or secrets.
