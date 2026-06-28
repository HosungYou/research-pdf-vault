---
name: research-review-queue
description: Triage and resolve Research PDF Vault review queue items with the review CLI or MCP review tools while preserving audit-friendly reasons and public-safe summaries.
---

# Research Review Queue

## When To Use

Use this skill when a user asks to inspect, approve, reject, reclassify, or merge review queue items created by Research PDF Vault.

## Safety Boundary

Review work is based on queue records, triage output, and generated summaries. Do not open source PDFs, do not perform direct OCR, do not perform direct PDF vectorization, and do not launch persistent worker services.

The public default is Red-only manual review. Amber can be added back only when `manual_review_lanes` explicitly includes `amber`.

## CLI Workflow

List pending items:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py review list --config fixtures/config/sample-config.toml
```

Show one item:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py review show queue_001 --config fixtures/config/sample-config.toml
```

Approve an item:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py review approve queue_001 --actor reviewer --reason "metadata verified" --config fixtures/config/sample-config.toml
```

Reject an item:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py review reject queue_001 --actor reviewer --reason "duplicate or out of scope" --config fixtures/config/sample-config.toml
```

Reclassify an item:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py review reclassify queue_001 --lane amber --actor reviewer --reason "needs manual confirmation" --config fixtures/config/sample-config.toml
```

Merge duplicates:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py review merge queue_001 paper_002 --actor reviewer --reason "same record" --config fixtures/config/sample-config.toml
```

Expected mutation observable: `review ok:` followed by queue item, paper ID, lane, and status.

For Discord-safe alert previews:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py notify discord --event review-queue --dry-run --config fixtures/config/sample-config.toml
```

## MCP Workflow

When the MCP server is available, prefer structured review tools for agent workflows:

- `list_review_queue` to retrieve local queue records.
- `apply_review_decision` to apply approve, reject, reclassify, or merge decisions.

Always include an actor and a concise reason. Never apply a decision from a filename alone; use the queue item details and generated triage context.

## Reporting

Summaries should group items by lane, status, priority, and reason. Keep output public-safe by using synthetic IDs and omitting personal paths, institutional strings, real PDF names, and secrets.
