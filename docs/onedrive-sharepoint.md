# OneDrive and SharePoint Notes

Research PDF Vault can index files from a locally synced folder when the user configures that folder as a storage root. The repository must never include a real sync path, tenant name, site name, drive id, document library name, or account identifier.

## Public Examples

Use placeholders only:

```toml
storage_roots = ["<vault-root>/<library-name>"]
cache_root = "<cache-root>/research-pdf-vault"
manifest_db = "<cache-root>/research-pdf-vault/manifest.sqlite3"

[sync]
provider = "onedrive_local"
dry_run_metadata_only = true
```

## Operational Guidance

- Prefer a local cache outside synced folders to avoid uploading derived artifacts.
- Keep OCR, extraction, FTS5, and embedding artifacts out of shared folders unless the user explicitly accepts that policy.
- Do not assume that a synced file is safe to index. Classification and review rules still apply.
- Keep offline/test mode on synthetic folders and fixture metadata.
- Use `scan --once --dry-run` before the first full-library ingest. Dry-run records file metadata and provider status without hashing or reading PDF bodies.
- Treat sync-conflict and cloud-only files as pending until the provider has delivered a stable local copy.
