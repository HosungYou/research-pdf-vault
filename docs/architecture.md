# Architecture

Research PDF Vault is a local plugin with a small data pipeline:

1. Configuration points to local storage roots and a local cache root.
2. Scanning records paper instances and stable fingerprints.
3. Extraction reads PDF text or optional OCR output.
4. Classification assigns privacy lanes before downstream indexing.
5. The manifest stores metadata, review state, artifacts, and audit rows in SQLite.
6. Retrieval uses SQLite/FTS5 and optional local embedding indexes.
7. Literature-map graph tables connect papers, claims, and support relationships.
8. MCP tools expose read-only summary/search surfaces plus constrained review decisions.

## Runtime Boundaries

- Python 3.11+ is the supported runtime.
- SQLite is the durable local store, and FTS5 is the text-search layer.
- OCRmyPDF and Tesseract are optional system dependencies for scanned PDFs.
- Embedding support is optional. Public fixtures use the `fixture` backend so tests are deterministic.
- offline/test mode must not call network services or require user documents.

## Privacy Lanes

Green records may expose approved metadata and allowed excerpts. Amber records are automated by default but can be placed back into manual review through config. Red records are metadata-only: text extraction, vector indexing, and external export are blocked.

## Public Fixtures

Fixtures in this repository are synthetic and original. They must not include real user PDFs, copied article excerpts, personal paths, cloud library names, organization names, secrets, or real metadata.
