# Research PDF Vault MCP Tools

The plugin exposes a local stdio MCP surface through `plugins/research-pdf-vault/scripts/mcp_server.py`. The server reads the configured local `manifest_db` from the selected vault config. It does not call network APIs and no v1 MCP tool runs scan, OCR, extraction, embedding, vector indexing, or batch ingestion jobs.

Red-lane records are metadata-only. Requests for Red full text return quarantine status and no passage text.

## Server Wiring

`plugins/research-pdf-vault/.mcp.json` registers:

```json
{
  "mcpServers": {
    "research-pdf-vault": {
      "command": "python3",
      "args": ["./scripts/mcp_server.py"],
      "cwd": "."
    }
  }
}
```

The script supports `initialize`, `tools/list`, `tools/call`, and `ping` over line-delimited JSON-RPC-style stdio. `--self-test --config <path>` runs a synthetic local manifest self-test without mutating fixture databases.

## Tools

### `get_manifest_summary`

Input schema: empty object.

Output schema: object with `counts`, `lanes`, `review_queue`, `privacy`, and `long_running_jobs`.

Read/write behavior: read-only. Reads `paper`, `paper_instance`, `review_queue_item`, and `worker_report` counts from the configured local manifest. If the manifest is absent, returns zero counts.

Audit behavior: no audit row is written.

### `search_papers`

Input schema: `{ "query": string, "limit"?: integer }`, where `limit` must be 1 through 50.

Output schema: `{ "query": string, "results": PaperSearchResult[] }`. Each result includes `paper_id`, `title`, `lane`, `metadata_only`, `quarantine_status`, and `snippets`.

Read/write behavior: read-only. Searches paper title, identifiers, and non-Red extracted passages. Red results never include snippets.

Audit behavior: no audit row is written.

### `get_paper`

Input schema: `{ "paper_id": string, "include_full_text"?: boolean }`.

Output schema: object with `status`, `paper`, `instances`, `review`, `artifacts`, `quarantine_status`, `full_text_status`, and `passages`.

Read/write behavior: read-only. Reads local metadata, review state, artifact state, and allowed passages. For Red papers, `include_full_text: true` returns `full_text_status: "metadata_only"`, `quarantine_status: "quarantined"`, and an empty `passages` list.

Audit behavior: no audit row is written.

### `list_review_queue`

Input schema: `{ "limit"?: integer }`, where `limit` must be 1 through 50.

Output schema: `{ "items": ReviewQueueItem[] }`. Each item includes queue id, paper id, title, lane, stage status, priority, reason, and created timestamp. Red reasons are redacted to metadata-only quarantine text.

Read/write behavior: read-only. Reads existing local review queue rows only.

Audit behavior: no audit row is written.

### `apply_review_decision`

Input schema: `{ "identifier": string, "decision": "approve" | "reject" | "defer" | "quarantine", "actor": string, "reason": string, "timestamp": string, "allow_sensitive"?: boolean }`.

Output schema: applied result `{ "status": "applied", "item": ReviewQueueItem }`, refused result `{ "status": "refused", "reason": string }`, or missing result `{ "status": "missing", "identifier": string }`.

Read/write behavior: the only v1 mutating MCP tool. It initializes the schema if needed, syncs missing Amber/Red queue rows, updates `review_queue_item`, and writes `audit_log`. It does not update `paper`, `classification_decision`, text artifacts, OCR artifacts, vector artifacts, or reports.

Audit behavior: writes one `audit_log` row for applied or refused decisions. `approve` maps to `release`, `reject` and `defer` map to `update`, and `quarantine` maps to `quarantine`. A Red approve without `allow_sensitive: true` is refused and audited as quarantine.

### `list_reports`

Input schema: empty object.

Output schema: `{ "reports": WorkerReport[] }`.

Read/write behavior: read-only. Reads local `worker_report` rows ordered by finish time.

Audit behavior: no audit row is written.

### `get_report`

Input schema: `{ "report_id": string }`.

Output schema: `{ "status": "ok", "report": WorkerReport }` or `{ "status": "missing", "report_id": string }`.

Read/write behavior: read-only. Reads a single local `worker_report` row.

Audit behavior: no audit row is written.
