# Research PDF Vault

Research PDF Vault is a local-first Codex plugin scaffold for indexing a personal research PDF collection. It keeps source files, extracted text, review status, and retrieval indexes under user-selected local paths.

The project is designed for public release with synthetic fixtures only. Repository examples use placeholders such as `<vault-root>`, `<cache-root>`, `<manifest-db>`, and `<library-name>`.

## Requirements

- Python 3.11+.
- SQLite with FTS5 enabled.
- Optional OCRmyPDF and Tesseract for OCR workflows.
- Optional local embedding models for vector search.
- offline/test mode through synthetic fixtures and the `fixture` embedding backend.

No cloud account is required for the default fixture workflow. External model calls and cloud cache use are disabled unless a local configuration explicitly enables them.

## Repository Layout

- `plugins/research-pdf-vault/`: plugin metadata and local Python scripts.
- `schemas/`: JSON Schemas for public artifact contracts.
- `fixtures/`: synthetic PDFs, metadata, configs, and test records.
- `docs/`: architecture, privacy, storage, dependency, model, copyright, and release notes.
- `tests/`: pytest coverage for schema, scanning, privacy lanes, review flow, and public hygiene.

## Quick Check

```bash
python3 -m pytest tests/test_public_hygiene.py
```

## Marketplace-Local Pilot

Start with a local OneDrive-synced source folder and a cache outside sync:

```toml
storage_roots = ["<local-sync-root>/<library-name>"]
cache_root = "<local-cache-root>/research-pdf-vault"
manifest_db = "<local-cache-root>/research-pdf-vault/manifest.sqlite3"

[sync]
provider = "onedrive_local"
dry_run_metadata_only = true

[approval]
manual_review_lanes = ["red"]

[notifications]
discord_enabled = false
discord_webhook_env = "RPV_DISCORD_WEBHOOK"
```

Run the first pass without reading PDF bodies:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py scan --once --dry-run --config <config-path>
```

Then run one-shot processing, inspect Red-only review pressure, and build a literature map:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py ingest --once --config <config-path>
python3 plugins/research-pdf-vault/scripts/rpv.py notify discord --event review-queue --dry-run --config <config-path>
python3 plugins/research-pdf-vault/scripts/rpv.py literature-map build --config <config-path>
python3 plugins/research-pdf-vault/scripts/rpv.py literature-map report --config <config-path>
python3 plugins/research-pdf-vault/scripts/rpv.py model-benchmark profiles
```

For a full public hygiene pass, also run:

```bash
rg -n "<private-path>|<organization-name>|<library-name>|<paper-title>" .
git diff --check
```

Use project-specific private strings only in local configuration outside this repository.

## Privacy Defaults

The sample configuration uses local storage roots, a local cache root, a local SQLite manifest database, `ocr_engine = "none"`, `embedding_backend = "fixture"`, `local_llm_backend = "disabled"`, and cloud cache disabled. Red-lane content is metadata-only and should not be embedded, exported, or sent to external systems.

See [docs/privacy-policy.md](docs/privacy-policy.md) for the release policy.
