# Sprint 07–15 backend QA audit

## Result

No open P0 or P1 issue remains in the local backend contract. The audit found
one P1 and two P2 issues, all fixed with regression coverage. Sequential QA
remediation P1-A additionally added a read-only search preflight contract so a
client can resolve every selected-document conflict before opening REST/SSE
search.

| Priority | Finding | Reproduction | Resolution |
| --- | --- | --- | --- |
| P1 | Candidate exploration used the full derived segment set even when the document was in the bounded `SAMPLE` comparison policy. A proposal could therefore embed more than `RAG_PORTAL_COMPARISON_CHUNK_THRESHOLD` chunks before explicit finalization. | Set `RAG_PORTAL_COMPARISON_CHUNK_THRESHOLD=3`, upload a long document, then create exploration proposals. | Exploration candidates now use the same deterministic sampled segments, preserve `SAMPLE`, and retain the true estimated chunk count. `test_exploration_preserves_large_document_sample_bound` guards it. |
| P2 | A legacy persisted job missing operational retry fields could make restore fail if `RAG_JOB_MAX_ATTEMPTS` or `RAG_JOB_RETRY_BACKOFF_SECONDS` was malformed, because restore parsed the environment directly. | Restore a pre-Sprint-14 job snapshot with either field absent and an invalid environment value. | Restore uses the validated job-setting helpers. `test_job_operational_environment_defaults_tolerate_invalid_values` covers the configuration fallback. |
| P2 | Exploration indexed a candidate before adding it to the document candidate list, so its model provenance could omit that proposal's retrieval configuration. | Create an exploration whose retrieval variant is new for the document, then inspect `provenance.model.retrieval_configs`. | Register the candidate before indexing, matching the normal creation path. The exploration regression asserts all proposed retrieval configurations are present in document provenance. |
| P1-A (fixed) | Clients had to invoke search (or open the SSE endpoint) to discover a selected document was not finalized, missing, or still waiting for full reindex. A multi-document UI could not obtain all actionable conflicts in one read-only response. | Select a sampled finalized document with a pending full-reindex plus a missing document ID. | `GET /rag-instances/{id}/search/preflight?document_ids=…` reuses the exact REST/SSE validation facts, returns per-document machine-readable `code`, `action`, and `full_reindex`, and never retrieves, generates, or persists an answer. Existing REST/SSE errors stay unchanged. `test_search_preflight_reports_per_document_conflicts_without_generating` guards it. |

## Local pass evidence

Executed from `apps/backend` with isolated SQLite files:

```text
RAG_PORTAL_DB_PATH=.rag-sprint715-qa.sqlite3 .venv/bin/pytest -q tests/test_api.py
33 passed

RAG_PORTAL_DB_PATH=.rag-sprint715-qa-full.sqlite3 .venv/bin/pytest -q
33 passed, 2 skipped

python3 -m compileall -q app
git diff --check
```

The two skipped tests are the deliberate external release-gate tests; see
below. The test suite also validates OpenAPI paths for the new job and
exploration contracts.

## Contract audit coverage

| Area | Evidence inspected/executed | Result |
| --- | --- | --- |
| Sprint 07 benchmark/runtime | embedding benchmark persistence, runtime catalog/execution-plan tests, candidate vector preparation | Pass with deterministic/local fallback labels retained. |
| Sprint 08 large documents | sample limit, full-reindex scheduling, search eligibility, persistence, plus the new exploration bound regression | Pass. No sampled candidate is treated as full-index-ready. |
| Sprint 09 grounded generation | retrieved-context-only generator contract, sentence citations, fallback metadata | Pass in deterministic tests; provider fallback remains explicit. |
| Sprint 10 multi-document search | per-document finalized retrieval configuration, merged/reranked context, grouped citations | Pass. |
| Sprint 11 release gate | strict opt-in E2E gate tests and isolated DB requirement inspected; default full suite skips without services | Gate is correctly guarded; actual provider execution is blocked by absent endpoints. |
| Sprint 12 feedback/retuning | retuning baseline/run/outcome artifacts, observation facts, explicit vote/finalize | Pass; no model-quality claim is inferred from observation data. |
| Sprint 13 reproducibility | checksum-addressed source storage, dedup, parser/chunk/model provenance, reparse baseline/history | Pass. |
| Sprint 14 jobs | durable state/idempotency, thread fallback, backoff/dead-letter/recovery, job-platform observability | Pass. Invalid operational setting fallback hardened in this QA pass. |
| Sprint 15 exploration | bounded pool/proposals, no auto selection, artifact/ledger, archive rollback and restore | Pass. The new sample-bound regression closes the large-document gap. |

## Actual-runtime gates blocked in this workspace

No `RAG_RELEASE_GATE`, embedding endpoint, reranker endpoint, generator
endpoint, or isolated release-runtime DB environment variable is configured in
this QA environment. Consequently it is not valid to claim provider-backed
embedding, cross-encoder reranking, grounded generation, or OCR release-gate
success here.

To run the real gate, provision every endpoint and use an isolated snapshot:

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

The optional OCR fixture additionally requires locally installed Tesseract
`kor` and `eng` language data and an available font. These are deployment gates,
not unit-test failures.
