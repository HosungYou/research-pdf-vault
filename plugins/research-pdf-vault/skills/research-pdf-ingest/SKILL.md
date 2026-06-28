---
name: research-pdf-ingest
description: Use the Research PDF Vault CLI to check setup, scan configured storage roots, run one-shot ingestion, and summarize generated reports without exposing private file paths or source documents.
---

# Research PDF Ingest

## When To Use

Use this skill when the user wants to initialize, check, scan, or ingest a local research PDF vault through the plugin CLI. Keep the workflow local, explicit, and report-driven.

## Safety Boundary

Codex should operate the vault through the documented CLI and generated report surfaces. Do not inspect private PDFs directly, do not perform direct OCR, do not perform direct PDF vectorization, and do not launch persistent worker services. Use the CLI to produce artifacts, then read the public-safe summaries and triage outputs.

## Setup Check

Prefer a setup check before scans or ingestion:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py setup --check --config fixtures/config/sample-config.toml
```

Expected observable: `config ok:` plus cache and manifest locations.

## Scan

Run one-shot scans only:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py scan --once --config fixtures/config/sample-config.toml
```

Expected observable: `scan ok:` with `scanned`, `ready`, and `pending` counts.

For OneDrive-style local sync roots, run metadata-only dry-run before the first full-library ingest:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py scan --once --dry-run --config fixtures/config/sample-config.toml
```

Expected observable: `dry_run` count. Dry-run must not hash or read PDF bodies.

## Ingest

Run one-shot ingestion when the user asks to build local searchable artifacts from the configured vault:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py ingest --once --config fixtures/config/sample-config.toml
```

Expected observables:

- `ingest ok:` with scan counts.
- `index ok:` with indexed, chunk, vector, quarantined, and skipped counts.

## Report Handling

After a scan or ingest, summarize generated reports and triage output instead of reading source PDFs. If MCP is available, use report summary tools such as `list_reports` and `get_report` for local report metadata. Keep summaries limited to paper IDs, lane/status counts, quarantine flags, and remediation steps.
For literature-map output, use `rpv.py literature-map build` and `rpv.py literature-map report` instead of reading PDFs directly.

## Public-Safe Output

- Use relative example paths only.
- Do not include personal directory names, institutional names, secrets, or real PDF titles.
- Replace sensitive source filenames with synthetic labels such as `paper_001` or `artifact_001`.
