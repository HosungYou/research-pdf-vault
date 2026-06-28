# Research PDF Vault Review Queue Alert Prompt

## Purpose

Notify a human when generated review queue output shows items that need manual action.

## Inputs

- `rpv.py review list` output.
- `rpv.py notify discord --event review-queue --dry-run` output.
- Optional `rpv.py review show <identifier>` details.
- Optional MCP `list_review_queue` output.

## Boundary

This automation reads generated queue and triage output only. It avoids direct OCR, direct PDF vectorization, and persistent worker service launch.

## Instructions

1. Count review items by lane, priority, and reason.
2. Identify Red-lane items that need a human decision.
3. Suggest the exact next review command for each action class:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py review show queue_001 --config fixtures/config/sample-config.toml
```

4. Include mutation command examples only as options for a human reviewer:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py review approve queue_001 --actor reviewer --reason "metadata verified" --config fixtures/config/sample-config.toml
```

## Output Format

- `Alert`
- `Queue Summary`
- `Needs Decision`
- `Suggested Commands`

Use synthetic queue and paper IDs only. Do not include personal paths, institutional strings, real PDF names, or secrets.
For Discord output, include counts and commands only.
