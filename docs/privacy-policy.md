# Privacy Policy

This project is local-first. By default, it reads from configured local storage roots, writes a local cache, and stores metadata in a local SQLite database.

## Data Handling

- Do not commit real PDFs, extracted full text, copied excerpts, user notes, cloud sync paths, secrets, or real library metadata.
- Use placeholders for paths, account names, library names, and paper titles in public docs.
- Keep Red-lane records metadata-only. Red content is not embedded, exported, or returned as full text.
- Keep offline/test mode deterministic with synthetic fixtures.
- Treat OCR outputs as derived document content and apply the same lane rules as source PDFs.

## Network and Model Use

External model calls are disabled by default. Optional local embedding models may be used when configured by the user. Cloud cache and external PDF upload settings must remain opt-in.

## Release Hygiene

Before public release, run the public hygiene tests and a repository string scan for private paths, organization names, cloud library identifiers, secrets, real paper titles, and copied excerpts.
