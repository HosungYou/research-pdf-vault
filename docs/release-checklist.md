# Release Checklist

Run these checks before publishing a branch, archive, or plugin package.

## Documentation

- README describes Python 3.11+, SQLite/FTS5, optional OCRmyPDF/Tesseract, optional local embedding models, and offline/test mode.
- Architecture, privacy, storage, model, dependency, copyright, and release docs are present.
- Examples use placeholders only.

## Fixtures

- Fixtures are synthetic and original.
- No fixture contains real PDFs, copied excerpts, personal paths, organization strings, cloud library names, secrets, or real metadata.

## Commands

```bash
python3 -m pytest tests/test_public_hygiene.py
python3 -m pytest tests/test_public_hygiene.py --cache-clear
python3 plugins/research-pdf-vault/scripts/rpv.py scan --once --dry-run --config fixtures/config/sample-config.toml
python3 plugins/research-pdf-vault/scripts/rpv.py notify discord --event review-queue --dry-run --config fixtures/config/sample-config.toml
python3 plugins/research-pdf-vault/scripts/rpv.py literature-map build --config fixtures/config/sample-config.toml
python3 plugins/research-pdf-vault/scripts/rpv.py literature-map report --config fixtures/config/sample-config.toml
python3 plugins/research-pdf-vault/scripts/rpv.py model-benchmark profiles
git diff --check
rg -n "<private-path>|<organization-name>|<library-name>|<paper-title>" .
```

If plugin metadata or executable plugin structure changes, run the plugin validation command documented for that change before release.
