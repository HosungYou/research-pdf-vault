# Dependency Policy

The project targets Python 3.11+ and standard local components first.

## Required

- Python 3.11+.
- SQLite with FTS5.
- pytest for the test suite.
- offline/test mode for deterministic public hygiene checks.

## Optional

- OCRmyPDF for OCR orchestration.
- Tesseract as the OCR engine used by OCRmyPDF.
- Local embedding models for private retrieval experiments.

## Release Rules

- Prefer standard-library behavior and pinned, documented dependencies.
- Keep optional dependencies optional in docs, tests, and fixture workflows.
- Do not make public hygiene tests depend on network access, cloud accounts, or real PDFs.
- Document any dependency that can read, upload, cache, or transform document content.
