# Sprint 11 — Release-gate E2E and honest runtime boundaries

## Outcome

Sprint 11 adds an opt-in backend release gate that uses provisioned model services without test doubles. It is intentionally separate from the normal local regression suite: a hash embedding, heuristic reranker, extractive fallback, or unavailable configured runtime cannot be mistaken for release evidence.

## Run

Start the required model services, set an isolated SQLite path, and run:

```bash
cd apps/backend
export RAG_PORTAL_DB_PATH=/absolute/path/release-gate.sqlite3
export RAG_EMBEDDING_URL_BGE_M3=http://127.0.0.1:8081
export RAG_EMBEDDING_URL_QWEN3_EMBEDDING_0_6B=http://127.0.0.1:8082
export RAG_EMBEDDING_URL_EMBEDDINGGEMMA_300M=http://127.0.0.1:8083
export RAG_RERANKER_URL=http://127.0.0.1:8084
export RAG_GENERATOR_URL=http://127.0.0.1:8085
bash scripts/release_gate.sh
```

The script writes JUnit XML to `release-gate-junit.xml` by default; set `RAG_RELEASE_GATE_REPORT_PATH` to retain it elsewhere. Set `RAG_RELEASE_GATE_JOB_TIMEOUT_SECONDS` for slow provisioned hardware.

`tests/test_release_gate_e2e.py` is skipped with an explicit message when no release endpoint is configured. If `RAG_RELEASE_GATE=1` or any release endpoint is configured, every required endpoint environment variable is mandatory. Every configured runtime must report `READY`; the benchmark must report `COMPLETED` with `local-tei`; and generation/reranking must not use fallback metadata. These conditions fail the test rather than skipping it.

## Covered evidence

- Runtime health for all three embeddings, reranker, and grounded generator.
- Actual three-model benchmark with no fallback provider.
- Text upload, parsing, candidate indexing, comparison, vote/finalization, a grounded single-document search, and a grounded multi-document search with `dense` and `hybrid_rerank` final candidates.
- Actual DOCX and PDF parsing above a forced bounded-comparison threshold, followed by finalization, `FULL_REINDEX`, and a post-reindex grounded search.
- OCR image upload when both Tesseract `kor` and `eng` language data plus a usable host font are available. That optional test is skipped with its exact missing-host reason; it never claims an OCR pass without the runtime.

The JUnit properties retain runtime service states, benchmark run ID, fixture SHA-256 values, answer artifact IDs, and full-reindex job/artifact IDs for the real run.

## Full-reindex search policy

The release policy is **strict blocking**. A candidate selected from a bounded `SAMPLE` comparison cannot answer from its old sampled index after finalization:

- Document `full_reindex` payloads expose `search_eligible`, `search_policy: BLOCK_UNTIL_FULL_INDEX_SUCCEEDED`, and the next action.
- REST and SSE share the same preflight. Active work returns HTTP `409 FULL_REINDEX_PENDING`; failed/cancelled work returns HTTP `409 FULL_REINDEX_FAILED` with the job ID, state, policy, and wait/retry action.
- After `SUCCEEDED`, normal search resumes from the full retained source index.

## SSE truthfulness and cancellation

The server now emits `status: RETRIEVING` before blocking work and `status: ANSWER_READY` before citations/tokens. The current generator API is non-streaming request/response, so the token events have `delivery: BUFFERED_REPLAY`; no claim is made that they arrive while the model is generating. This preserves the more important guarantee that no text is emitted before grounding validation.

A client disconnect stops future SSE emission when observed, but cannot cancel an already active synchronous provider request. That request can still finish and persist an `ANSWER` artifact. There is no server-side search-cancel endpoint today. A future token-streaming/cancellable generator protocol must carry cancellation through embedding, reranking, generation, and artifact policy before this can change.

## Local regression

The ordinary suite remains model-independent:

```bash
cd apps/backend
.venv/bin/python -m pytest -q tests
```

Expected in an unprovisioned environment: core tests pass and the two release-gate tests skip explicitly.
