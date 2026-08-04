# Sprint 07–10 targeted backend regression QA

## Result

The targeted regression pass found and fixed one P1 in grounded generation.
No open P0/P1 regression remains in the locally executable contracts.

| Priority | Finding | Reproduction | Fix and regression coverage |
| --- | --- | --- | --- |
| P1 (fixed) | A generator response with an empty `sentences` list passed validation, producing a `grounded: true` empty answer with no citations instead of an explicit fallback. | Return `GenerationResult(sentences=[])` from a configured generator path. | Empty output is now rejected as `INVALID_GROUNDING`, yielding the existing cited extractive fallback for REST and SSE. `test_empty_generation_is_rejected_and_uses_cited_fallback` covers both transports. |

## Exact local test evidence

Executed from `apps/backend` against an isolated SQLite snapshot:

```text
RAG_PORTAL_DB_PATH=.rag-sprint0710-qa-final.sqlite3 \
  .venv/bin/pytest -q tests/test_api.py \
  -k 'embedding_benchmark or model_runtime or large_document or model_generation or invalid_or_failed_generation or empty_generation or full_reindex_search_policy or multi_document or candidate_pipelines or ungrounded_query'

13 passed, 22 deselected
```

The selected tests cover:

| Sprint | Contract checked | Result |
| --- | --- | --- |
| 07 | Benchmark persistence, runtime/execution-plan visibility, distinct persisted candidate chunks and retrieval index use. | Pass. Benchmark remains persisted as observation data, not a fabricated quality score. |
| 08 | Large-document bounded `SAMPLE` candidate indexing, full-reindex artifact/job, strict REST/SSE eligibility before full indexing. | Pass. |
| 09 | Grounded REST answer context restriction, citation IDs, invalid/unavailable/empty generator fallback, and buffered SSE citation/token events. | Pass after the empty-generation P1 fix. |
| 10 | Per-document retrieval configuration, normalized merge, grouped citations, persisted multi-document artifacts, and fallback restricted to selected evidence. | Pass. |

## Actual-runtime gates

This workspace has no configured `RAG_RELEASE_GATE`, embedding endpoint,
reranker endpoint, or generator endpoint. The deterministic/local tests verify
contracts and explicit fallback behavior, but cannot certify provider-backed
embedding, cross-encoder reranking, or model generation.

Run the opt-in external gate with provisioned endpoints and an isolated DB:

```bash
RAG_RELEASE_GATE=1 \
RAG_PORTAL_DB_PATH=.rag-release-gate.sqlite3 \
RAG_EMBEDDING_URL_BGE_M3=http://... \
RAG_EMBEDDING_URL_QWEN3_EMBEDDING_0_6B=http://... \
RAG_EMBEDDING_URL_EMBEDDINGGEMMA_300M=http://... \
RAG_RERANKER_URL=http://... \
RAG_GENERATOR_URL=http://... \
.venv/bin/pytest -q tests/test_release_gate_e2e.py
```

The release OCR fixture also requires Tesseract with `kor` and `eng` language
data. These are external deployment gates, not local test failures.
