---
name: research-pdf-save
description: Save or structure research PDFs through Research PDF Vault. Use when the user asks to save, import, sync, structure, use, or organize a paper/PDF in the vault, explicitly or implicitly, while preserving local-first storage and approval gates.
---

# Research PDF Save

## Purpose

Turn a paper/PDF saving request into the safest Research PDF Vault action. Prefer automatic local organization when the action is already authorized by the current user request. Stop only for high-risk actions.

## Trigger Interpretation

Use this skill when the user says or implies:

- save this paper/PDF
- import this PDF
- structure this paper
- use this PDF for the vault
- organize the downloaded paper
- `$save` or `/save`
- a PDF was found during search and should be kept

Implicit save is allowed when the current task clearly produced or identified a local PDF artifact that belongs in the vault. Do not ask for redundant approval for low-risk local actions.

## Storage Boundary

Original PDFs belong only under the configured `storage_roots`.

Preferred intake target:

```text
<storage_root>/inbox/
```

The agent must not store source PDFs in `cache_root`, the Git repository, temporary project folders, or generated artifact folders. `cache_root` is for derived data only: manifest DB, extraction outputs, OCR outputs, embeddings, construct registry exports, and reports.

## Approval Gate

Proceed without asking when the action is local and non-destructive:

- resolve DOI metadata
- compute PDF hash
- detect duplicates
- import a user-supplied local PDF into `<storage_root>/inbox/`
- run one-shot scan/ingest after import
- generate local-only structure candidates
- write generated summaries or registry exports under `cache_root`

Treat current-session user wording as approval when it directly asks to save/import/use a local PDF.

Ask explicit approval before:

- using a logged-in browser session to access or download a PDF
- downloading from a publisher site
- using institutional, paid, or gated access
- deleting, moving, or renaming existing source PDFs
- sending PDF body text or long excerpts to external services
- processing Red-lane body text
- confirming construct merges

When asking, state exactly the action, source, destination, and risk. Ask for a one-word approval.

## Workflow

1. Locate the vault config. Prefer the user-supplied config path. Otherwise use the project fixture only for examples.
2. Identify whether the input is a local PDF, DOI, URL, browser/download artifact, or already-ingested paper ID.
3. Apply the approval gate.
4. For a local PDF import, copy or move only through the Research PDF Vault CLI when an import command exists. If the CLI lacks import support, report the required command shape instead of hand-copying private PDFs.
5. Run one-shot ingestion through the CLI:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py ingest --once --config <config-path>
```

6. When structure is requested or implied, build construct candidates and refresh the literature map:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py constructs build --config <config-path>
python3 plugins/research-pdf-vault/scripts/rpv.py constructs export --config <config-path>
python3 plugins/research-pdf-vault/scripts/rpv.py constructs review list --config <config-path>
python3 plugins/research-pdf-vault/scripts/rpv.py literature-map build --config <config-path>
python3 plugins/research-pdf-vault/scripts/rpv.py literature-map report --config <config-path>
```

7. Report observable counts: scanned, ready, pending, construct registry count, construct candidate count, review-required count, export paths, pending construct review rows, and literature-map node/edge counts.

## DOI Handling

DOI is metadata/provenance, not download permission.

- `resolve-doi`: metadata enrichment only.
- `import`: user-supplied local PDF only.
- `download`: separate high-risk action requiring explicit approval.

## Structure Handling

When asked to structure after saving, prioritize construct-centered organization:

- `reported_term`
- `candidate_normalization`
- `measurement_proxy`
- `theoretical_role`
- candidate link to `construct_registry`

Low-confidence construct links, theoretical role conflicts, measurement family conflicts, and all construct merges require review.

Use review actions only when the user asks to decide a candidate:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py constructs review approve <candidate_id> --actor <actor> --reason <reason> --config <config-path>
python3 plugins/research-pdf-vault/scripts/rpv.py constructs review reject <candidate_id> --actor <actor> --reason <reason> --config <config-path>
python3 plugins/research-pdf-vault/scripts/rpv.py constructs review reassign <candidate_id> --construct <construct_id> --actor <actor> --reason <reason> --config <config-path>
```

## Public-Safe Output

Do not print private paths, institutional names, real paper titles, or long excerpts unless the user explicitly asks and the content is already local. Prefer IDs, counts, and sanitized relative locations.
