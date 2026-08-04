# RAG Portal MVP API

프론트엔드와 병렬 개발할 수 있도록 만든 로컬 실행용 FastAPI 백엔드입니다. 로그인은 이미 완료된 상태를 전제로 하며, 외부 LLM·벡터 DB 없이도 흐름 전체를 확인할 수 있는 로컬 실행 구현입니다. RAG 인스턴스, job, 비교 라운드, 투표와 결과물은 SQLite snapshot으로 프로세스 재시작 뒤에도 복원됩니다.

## Run

```bash
cd apps/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8010
```

API 문서는 [http://127.0.0.1:8010/docs](http://127.0.0.1:8010/docs), OpenAPI JSON은 `/api/v1/openapi.json`에 있습니다.

```bash
.venv/bin/pytest -q
```

## Local model server (recommended development baseline)

The API is designed on the assumption that free, open-weight model services are already running on the development server. The model registry is explicit:

The single source of truth for what is implemented versus what still needs to be provisioned is [Model Runtime Deployment](../../docs/MODEL_RUNTIME_DEPLOYMENT.md). Follow that checklist before declaring a development or production environment model-ready.

| Role | Model | Local TEI profile / port | When selected |
| --- | --- | --- | --- |
| Balanced multilingual embedding | `BAAI/bge-m3` | `bge` / 8081 | `BGE-M3` |
| Lightweight self-hosted embedding | `Qwen/Qwen3-Embedding-0.6B` | `qwen` / 8082 | `Qwen3-Embedding-0.6B` |
| Small-footprint embedding | `google/embeddinggemma-300m` | `gemma` / 8083 | `EmbeddingGemma-300M` |
| Cross-encoder reranker | `BAAI/bge-reranker-v2-m3` | `reranker` / 8084 | `hybrid_rerank` |
| Grounded answer generation | configured local generator | custom `/generate` / 8085 | search and tuning comparison |
| OCR language data | Tesseract `kor` + `eng` | host package | scanned PDF/image |

Download and run only the embedding profile(s) your development server needs, plus the shared reranker:

```bash
docker compose -f docker-compose.models.yml --profile bge --profile reranker up -d
```

The first start downloads model weights into the named volume. Copy `.env.example` to `.env`, then run Uvicorn with `--env-file .env` so the API is pointed at the matching local services. TEI exposes `/embed` for embeddings and `/rerank` for a model-backed cross-encoder reranker. [Hugging Face TEI quick tour](https://huggingface.co/docs/text-embeddings-inference/en/quick_tour)

The generator is a separately configured local service (`RAG_GENERATOR_URL`). It receives only retrieved `{segment_id, text}` context and must return sentence-level `citation_ids`; [Sprint 09](../../docs/SPRINT_09_GROUNDED_GENERATION.md) defines the HTTP contract and fallback behavior. For multiple finalized documents, each source is retrieved with its own finalized configuration, normalized before the global merge, and only the bounded selected context is sent to the generator; see [Sprint 10](../../docs/SPRINT_10_MULTI_DOCUMENT_SEARCH.md).

## Optional external integrations

Copy `.env.example` to `.env` and start the API with `uvicorn app.main:app --env-file .env` (or export the same values into its process).

- With `HF_TOKEN`, the worker can use Hugging Face Inference Providers only as a fallback when a local model service is unavailable. Without either service, the API visibly records a local hash-vector fallback for development; it does not claim semantic-quality equivalence.
- `RAG_QUEUE_BACKEND=redis` plus `REDIS_URL` uses the Redis dispatch adapter. `RAG_QUEUE_BACKEND=sqs` uses an SQS-compatible queue configured with `RAG_SQS_QUEUE_URL` (and optionally `RAG_SQS_ENDPOINT_URL`). Both queue message formats are `{job_id, idempotency_key}`; a production consumer calls `app.main.consume_dispatched_job(job_id, idempotency_key)`. If a configured adapter is unavailable, the service reports the reason in `GET /job-platform` and falls back to the local worker for development.
- `RAG_JOB_MAX_ATTEMPTS` bounds manual retries (default `3`) and `RAG_JOB_RETRY_BACKOFF_SECONDS` adds a retry gate (default `0`). Jobs that exhaust the budget become `DEAD_LETTER`; inspect them with `GET /rag-jobs/dead-letters` and use `POST /rag-jobs/{jobId}/recover` only after an operator has corrected the cause.
- PDF, DOCX, and XLSX are parsed from binary upload data. Scanned PDFs and images use PyMuPDF/Pillow + Tesseract OCR. Install the Tesseract executable with Korean and English language packs in the deployment environment; otherwise the job fails with an actionable OCR error that can be retried after installation.

## API contract

Base URL: `http://127.0.0.1:8010/api/v1`

| Flow | Endpoint | Notes |
| --- | --- | --- |
| Model recommendations | `POST /rag-instances/embedding-recommendations` | Returns three ranked, explainable model candidates before a user chooses one. |
| Model runtime | `GET /model-runtime` | Lists every parser/OCR/embedding/reranker service, its endpoint, and readiness state. |
| Large-document policy | `GET /large-document-policy` | Returns the configurable comparison chunk threshold (default 500) and sampling rule. |
| Execution plan | `GET /rag-instances/{id}/execution-plan` | Resolves the model services required by that instance's selected embedding model, document profiles, and retrieval techniques. |
| Dashboard | `GET/POST /rag-instances` | POST creates a `SETTING_UP` instance and persists the model selected from the candidate set. |
| Detail | `GET /rag-instances/{id}` | Includes documents, candidates, final choice. |
| Add mode choices | `GET /rag-instances/{id}/document-add-options` | Explains whether an existing finalized pipeline can be reused, and lists its eligible source documents. |
| Upload + process | `POST /rag-instances/{id}/documents` | JSON `documents[]` plus explicit `pipeline_mode`; decision/job metadata expose `FULL` or bounded `SAMPLE` comparison counts, then parser/candidate/index preparation proceeds in the background. |
| Reparse | `POST /rag-instances/{id}/documents/{documentId}/reparse` | Reuses the immutable stored original, captures `REPARSE_BASELINE`, then queues a cancellable/retryable `REPARSE` job and retains prior artifact provenance. |
| Candidate exploration | `POST,GET /rag-instances/{id}/candidate-exploration` / `GET,POST /candidate-exploration/{explorationId}` | Records a bounded, explainable candidate pool and proposes optional chunking/retrieval variants. It never votes, selects, or finalizes; rollback/restore only archives/reactivates exploration-created candidates. |
| Job polling | `GET /rag-jobs/{jobId}` / `GET /rag-instances/{id}/jobs` | State, completed stages, actual progress, retry/cancel availability, and linked artifact. |
| Job platform | `GET /job-platform` / `GET /rag-jobs/dead-letters` | Queue adapter readiness/fallback, job-state counts, latest worker heartbeat, and dead-letter inventory. |
| Job control | `POST /rag-jobs/{jobId}/cancel` / `POST /rag-jobs/{jobId}/retry` / `POST /rag-jobs/{jobId}/recover` | Stops at a checkpoint, retries within the configured bound/backoff, or explicitly recovers a dead-letter job. |
| Comparison | `POST /rag-instances/{id}/tuning/compare` | Returns 9 (3 chunking × 3 retrieval) answer cards per document with inline citations. Each candidate searches its own prepared chunks. |
| Vote | `POST /tuning-rounds/{id}/vote` | Multiple candidate IDs allowed. |
| Status | `GET /rag-instances/{id}/tuning-status?document_ids=id` | `can_finalize` only becomes true for a unique leader. |
| Finalize | `POST /rag-instances/{id}/tuning/finalize` | Deletes temporary losing candidates and records the winner; a sampled document also receives a persisted `FULL_REINDEX` job/artifact. Its document payload declares `search_eligible`, strict `BLOCK_UNTIL_FULL_INDEX_SUCCEEDED` policy, and the next wait/retry action. |
| Search | `POST /rag-instances/{id}/search` | Finalized documents only; default sensitivity is `balanced`. A sampled document is ineligible until full reindex succeeds: active work returns `409 FULL_REINDEX_PENDING`, failed/cancelled work returns `409 FULL_REINDEX_FAILED`, both with structured `full_reindex` details. Multi-document searches return flat compatibility citations plus `grouped_citations` and explainable per-document merge/rerank metadata. |
| Search stream | `GET /rag-instances/{id}/search/stream` | Preflight keeps the same HTTP reindex errors as REST, then emits `status` (`RETRIEVING`, `ANSWER_READY`), `citations`, buffered-safe token replay, and `done`. See [Sprint 11](../../docs/SPRINT_11_RELEASE_GATE.md) for generator streaming/cancellation limits. |
| Citation viewer | `GET /documents/{documentId}/segments/{segmentId}` | Opens source text at the exact cited offsets, with previous/next segment IDs. |
| Artifacts | `GET /rag-instances/{id}/artifacts` / `GET,DELETE /rag-instances/{id}/artifacts/{artifactId}` | Processing runs, comparisons, decisions, and answers are explicit objects with status, timestamps, context, and actions. |
| Feedback | `POST /rag-instances/{id}/feedback` / `GET /rag-instances/{id}/feedback-summary` / `GET /rag-instances/{id}/retuning-recommendation` | Optional answer/context feedback and a versioned, explainable re-tuning recommendation with feedback recency, stored answer-integrity observations, and benchmark/provider context. |
| Re-tune | `POST /rag-instances/{id}/retune` | Recreates comparison candidates after user confirmation while persisting `RETUNING_BASELINE`; the next comparison persists a comparable `RETUNING_OUTCOME`. |
| Document deletion | `DELETE /rag-instances/{id}/documents/{documentId}` | Cleans up candidate data and marks affected artifacts as `PARTIAL` or `UNAVAILABLE`. |

Upload body example:

```json
{
  "documents": [{
    "filename": "출장비_규정.txt",
    "content_type": "text/plain",
    "content": "제5조 해외 출장 식비는 1일 80~150달러입니다."
  }],
  "pipeline_mode": "retune"
}
```

Document add behavior is explicit rather than an implicit boolean:

```json
{
  "documents": [{"filename": "복리후생.txt", "content": "..."}],
  "pipeline_mode": "reuse",
  "reuse_from_document_id": "a-finalized-document-id"
}
```

Use `GET /rag-instances/{id}/document-add-options` before showing this choice. `reuse` is rejected when there is no finalized source; `retune` is always available. The legacy `reuse_finalized_pipeline` boolean is temporarily accepted for first-slice clients.

`content` JSON is deliberate for the first frontend slice. Swap this endpoint to multipart/object storage later without changing the instance, job, tuning, search, citation, or artifact contracts.

## Product behavior captured

- Questionnaire ranks a small embedding-model candidate set; the user selects one model per RAG instance, while GraphRAG remains instance-level.
- Upload automatically extracts PDF/DOCX/XLSX/text content (and uses OCR for scan/image sources when provisioned), profiles document shape, and creates 3 chunking × 3 retrieval candidates. Each candidate persists its own derived chunks and vector records, so structural, semantic, fixed-length, and table strategies are meaningfully comparable.
- JSON `content` and `content_base64` remain supported. Before parsing, their bytes are stored as an immutable checksum-addressed source object. The default adapter is local filesystem (`RAG_SOURCE_STORAGE_PATH=.rag-sources`); an authenticated path-style object-storage gateway can be selected with `RAG_SOURCE_STORAGE_BACKEND=object`. Within one instance, identical SHA-256 sources reuse the same stored object while retaining separate document records.
- Candidate generation is bounded to nine comparable options, but is not a fixed template: parser output measures headings, paragraphs, table-like rows, source length, and OCR use. Those measurements select the three chunking strategies and calculate each candidate's chunk size, overlap, section cap, or rows-per-chunk. The API returns the calculation and its human-readable reason in `chunking_analysis`, `chunking_parameters`, and `selection_reason`.
- Comparison gives answer-first cards with evidence; missing evidence refuses to fabricate an answer.
- Retrieved context is passed to the local generator as the only source material. Every generated sentence must cite a supplied segment ID; endpoint failure or invalid grounding is replaced by a clearly labeled extractive fallback.
- Multi-select vote accumulates counts. A tie cannot finalize.
- Finalization retains only the winner per document. Search follows citations and supports a three-level sensitivity setting.
- A `RETUNE` upload estimates chunks per strategy using `RAG_PORTAL_COMPARISON_CHUNK_THRESHOLD` (default `500`). Above that budget, candidate comparison uses deterministic source-wide samples while retaining the full source. Finalizing such a choice schedules a `FULL_REINDEX` job; search waits for that full index instead of serving the sample as a finished RAG.
- Each finished operation creates an artifact object (`PROCESSING_RUN`, `TUNING_COMPARISON`, `PIPELINE_DECISION`, `ANSWER`, `RETUNING_BASELINE`, `RETUNING_RUN`, or `RETUNING_OUTCOME`) suitable for an Output/Studio panel.
- Citations include a focusable navigation URL and exact text offsets; the viewer response exposes neighbouring source segments without moving the core workspace.
- Job stages are completed facts, not simulated percentages. The local worker parses uploaded text, creates profile-matched candidates, and prepares local retrieval state in the background.
- Negative feedback can include answer/artifact/document/citation context. The API uses versioned recency-weighted feedback plus stored answer-integrity events for `START_RETUNE`; benchmark/provider status is exposed as runtime context but never fabricated into a model-quality score. Re-tuning remains a separate, explicit action; see [Sprint 12](../../docs/SPRINT_12_FEEDBACK_RETUNING.md).
- Document detail exposes source checksum/storage/dedup information and parser, chunking, and model provenance. A reparse never overwrites old artifacts; it captures `REPARSE_BASELINE` and `REPARSE_RUN` history. See [Sprint 13](../../docs/SPRINT_13_SOURCE_REPRODUCIBILITY.md).
- Each durable job stores an idempotency key, dispatch receipt, worker heartbeat, execution count, retry schedule, and dead-letter reason. Duplicate Redis/SQS delivery is claimed once by the durable runner; `PROCESSING`, `REPARSE`, and `FULL_REINDEX` retain their existing stages and artifacts. See [Sprint 14](../../docs/SPRINT_14_OPERATIONAL_JOBS.md).
- Candidate exploration snapshots bounded readiness/vote/evidence signals and proposes temporary variants with transparent parameter deltas. It never auto-selects or auto-finalizes; rollback/restore affects only exploration-created candidates. See [Sprint 15](../../docs/SPRINT_15_ADAPTIVE_EXPLORATION.md).

## Intentional MVP boundaries

- SQLite snapshot persistence is local-process durability, not a multi-worker production database.
- The local worker uses pypdf/python-docx/openpyxl extraction, optional PyMuPDF/Tesseract OCR, candidate-specific chunking, a persisted vector index, BM25, dense, hybrid, and hybrid-rerank scoring. Its primary embedding/rerank path is a local TEI service with downloaded open models; Hugging Face provider access is only an optional fallback.
- A production deployment still needs a provisioned Redis/SQS service, object storage, provider credentials, and a model-backed reranker. The local fallback deliberately marks itself as a development baseline rather than a semantic or cross-encoder quality claim.
