# Research PDF Vault Citation-Slot Readiness Prompt

## Purpose

Notify a human when generated claim cards and citation slots are ready for drafting or need review.

## Inputs

- JSON output from:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py citation-slots build --config fixtures/config/sample-config.toml --project sample-aidt
```

## Boundary

This automation reads generated claim-card and citation-slot output only. It avoids direct OCR, direct PDF vectorization, and persistent worker service launch.

## Instructions

1. Count claim cards and citation slots.
2. Group slots by support tag.
3. Flag slots with weak, missing, conflicting, or ambiguous support.
4. Identify slots ready for human drafting.
5. Include the build command if fresh citation-slot output is needed.

## Output Format

- `Readiness`
- `Support Tags`
- `Ready Slots`
- `Needs Review`
- `Suggested Command`

Use synthetic project, claim, slot, and passage IDs only. Do not include personal paths, institutional strings, real PDF names, or secrets.
