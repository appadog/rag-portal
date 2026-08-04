# Sprint 07–10 backend audit

Audited: 2026-08-03. Scope: `docs/SPRINT_07_EMBEDDING_BENCHMARK.md` through `docs/SPRINT_10_MULTI_DOCUMENT_SEARCH.md`, their FastAPI contracts, SQLite snapshot state, fallback behavior, and backend tests. Frontend was not changed.

## Result

The four sprint contracts are implemented and align with the current backend. No product-contract defect was found. One runtime-readiness documentation gap was corrected during this audit:

- Sprint 09 now documents the `GET {RAG_GENERATOR_URL}/health` requirement used by `model-runtime`; `/generate` remains the only generation endpoint.

## Evidence by sprint

| Sprint | Contract evidence | Persistence / safety evidence |
| --- | --- | --- |
| 07 | `POST /embedding-benchmarks/run` executes all three configured embedding selections and records Recall@1, Recall@5, MRR, latency, dimension, provider, and explicit `FALLBACK`/`FAILED` status. `GET /embedding-benchmarks/latest` returns 404 `BENCHMARK_NOT_RUN` before any run. | `BENCHMARK_RUNS` is included in `state_payload()` and rehydrated in `restore_state()`. The benchmark endpoint test verifies run/latest behavior; snapshot serialization is directly covered by the common state implementation. |
| 08 | `GET /large-document-policy`, document comparison plans, `SAMPLE` selection, finalization-created `FULL_REINDEX`, retry/cancel/resume handling, and `409 FULL_REINDEX_PENDING` are present in `app/main.py`. Reuse constructs full-source chunks directly. | Documents, candidates, jobs, artifacts, comparison plans, and full-reindex state are serialized. `test_large_document_uses_bounded_sample_then_persists_full_reindex` verifies full indexing and restore. |
| 09 | `generate_grounded` sends only question plus `{segment_id, text}` contexts. `render_validated_generation` rejects uncited or unknown cited sentences. Search, comparison, artifacts, and SSE `done` expose generation state. | Request/malformed-response errors become `GenerationEndpointError`; invalid grounding becomes `EXTRACTIVE_FALLBACK` without exposing model text. Tests cover valid persistence and invalid/unavailable generation fallback. |
| 10 | Multi-document search retrieves each finalized candidate with its own config (or the explicit request override), applies per-document max normalization, uses per-document top-k reranking, globally merges candidates, and bounds generator context. It returns both flat and grouped citations with explainable retrieval metadata. | `ANSWER` metadata/payload contains grouped citations, retrieval metadata, and generation data; generic artifact snapshot persistence covers them. Tests assert cross-document ordering, citations, artifact/snapshot data, and invalid-generation fallback restricted to supplied evidence. |

## Verification

```text
cd apps/backend
.venv/bin/python -m pytest -q tests/test_api.py
```

Result after the audit change: `24 passed` (the existing deprecation warnings are from FastAPI/Starlette and PyMuPDF bindings, not test failures). `python -m compileall -q app` and `git diff --check` also pass.

## Remaining external-runtime gates

These are intentionally not represented as successful quality claims by local fallback tests:

1. Run the three configured embedding endpoints and confirm `local-tei` provider plus expected dimensions in a real development environment.
2. Run a reachable reranker for `hybrid_rerank`; without it, response metadata reports the local heuristic fallback.
3. Provide a grounded generator exposing both `/health` and `/generate`; otherwise generation is explicitly marked `EXTRACTIVE_FALLBACK` and the runtime catalog is not ready.
4. Install Tesseract with Korean/English language data before treating scanned PDF/image processing as production-ready.
5. Measure the configurable 500-chunk comparison threshold and multi-document context/rerank limits against representative source corpora before production rollout.
