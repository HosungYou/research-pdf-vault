# Local Model Notes

Research PDF Vault supports optional local embedding models for retrieval. Public tests use the `fixture` backend, which is deterministic and does not require downloading a model.

## Defaults

- `embedding_backend = "fixture"` for offline/test mode.
- `local_llm_backend = "disabled"` unless a user config enables a local service.
- `enable_external_models = false` for public fixtures and release checks.
- `model-benchmark profiles` lists Qwen as the default local benchmark family and GLM-4.5-Air as an explicit opt-in experimental profile.

## Local Embeddings

When a user chooses a local embedding backend, keep model files and generated vectors in local cache paths. Do not commit model weights, vector stores, prompts containing private excerpts, or generated summaries from real documents.

Red-lane records remain metadata-only even when local models are available.

## Benchmark Harness

Use dry-run first:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py model-benchmark profiles
python3 plugins/research-pdf-vault/scripts/rpv.py model-benchmark run --profile qwen-local-default --dry-run
```

Heavy profiles require an explicit flag:

```bash
python3 plugins/research-pdf-vault/scripts/rpv.py model-benchmark run --profile glm-4.5-air-experimental --dry-run --allow-heavy
```

The benchmark contract records classification accuracy, literature-map edge precision, tokens per second, peak memory, and failure rate. It never permits Red-lane PDF body text in benchmark inputs.
