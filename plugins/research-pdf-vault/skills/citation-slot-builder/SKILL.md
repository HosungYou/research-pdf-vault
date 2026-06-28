---
name: citation-slot-builder
description: Build Research PDF Vault claim cards and citation slots from configured fixture-backed retrieval output, then summarize support tags and readiness without exposing private PDFs.
---

# Citation Slot Builder

## When To Use

Use this skill when a user asks to generate, inspect, or summarize citation slots for a research project in the vault.

## Safety Boundary

Citation slot work reads configured retrieval outputs and generated claim-card data. Do not read source PDFs directly, do not perform direct OCR, do not perform direct PDF vectorization, and do not launch persistent worker services.

## Build Command

Run the citation slot builder through the CLI:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py citation-slots build --config fixtures/config/sample-config.toml --project sample-aidt
```

Expected observable: JSON containing `project`, `claim_cards`, and `citation_slots`.

## Review The Output

Inspect the generated JSON for:

- Claim cards: claim ID, normalized claim text, source passage IDs, and support tags.
- Citation slots: slot ID, claim ID, support tag, passage count, and readiness.
- Gaps: claims with weak support, missing passages, conflicting support tags, or ambiguous wording.

## Recommended Response Shape

When returning results to the user:

1. State the project ID and command run.
2. Summarize total claim cards and total citation slots.
3. Group citation slots by support tag.
4. Call out slots that need review before drafting.
5. Avoid quoting private source text unless the user supplied that text in the current conversation.

## Public-Safe Output

Use synthetic project IDs such as `sample-aidt` in examples. Do not include personal paths, institutional names, real PDF titles, or secrets.
