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

## API contract

Base URL: `http://127.0.0.1:8010/api/v1`

| Flow | Endpoint | Notes |
| --- | --- | --- |
| Dashboard | `GET/POST /rag-instances` | POST creates `SETTING_UP` instance and recommends one fixed embedding model. |
| Detail | `GET /rag-instances/{id}` | Includes documents, candidates, final choice. |
| Add mode choices | `GET /rag-instances/{id}/document-add-options` | Explains whether an existing finalized pipeline can be reused, and lists its eligible source documents. |
| Upload + process | `POST /rag-instances/{id}/documents` | JSON `documents[]` plus explicit `pipeline_mode`; returns a queued job immediately, then parser/candidate/index preparation proceeds in the background. |
| Job polling | `GET /rag-jobs/{jobId}` / `GET /rag-instances/{id}/jobs` | State, completed stages, actual progress, retry/cancel availability, and linked artifact. |
| Comparison | `POST /rag-instances/{id}/tuning/compare` | Returns 9 (3 chunking × 3 retrieval) answer cards per document with inline citations. Each candidate searches its own prepared chunks. |
| Vote | `POST /tuning-rounds/{id}/vote` | Multiple candidate IDs allowed. |
| Status | `GET /rag-instances/{id}/tuning-status?document_ids=id` | `can_finalize` only becomes true for a unique leader. |
| Finalize | `POST /rag-instances/{id}/tuning/finalize` | Deletes temporary losing candidates and records the winner. |
| Search | `POST /rag-instances/{id}/search` | Finalized documents only; default sensitivity is `balanced`. |
| Search stream | `GET /rag-instances/{id}/search/stream` | SSE events: `citations`, `token`, `done`. |
| Citation viewer | `GET /documents/{documentId}/segments/{segmentId}` | Opens source text at the exact cited offsets, with previous/next segment IDs. |
| Artifacts | `GET /rag-instances/{id}/artifacts` / `GET,DELETE /rag-instances/{id}/artifacts/{artifactId}` | Processing runs, comparisons, decisions, and answers are explicit objects with status, timestamps, context, and actions. |
| Feedback | `POST /rag-instances/{id}/feedback` / `GET /rag-instances/{id}/feedback-summary` | Optional answer/context feedback and an explicit re-tuning recommendation signal. |
| Re-tune | `POST /rag-instances/{id}/retune` | Recreates comparison candidates for finalized documents after user confirmation. |
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

- Questionnaire selects one embedding model per RAG instance; GraphRAG is instance-level.
- Upload automatically parses content, profiles document shape, and creates 3 chunking × 3 retrieval candidates. Each candidate persists its own derived chunks, so structural, semantic, fixed-length, and table strategies are meaningfully comparable.
- Comparison gives answer-first cards with evidence; missing evidence refuses to fabricate an answer.
- Multi-select vote accumulates counts. A tie cannot finalize.
- Finalization retains only the winner per document. Search follows citations and supports a three-level sensitivity setting.
- Each finished operation creates an artifact object (`PROCESSING_RUN`, `TUNING_COMPARISON`, `PIPELINE_DECISION`, `ANSWER`, or `RETUNING_RUN`) suitable for an Output/Studio panel.
- Citations include a focusable navigation URL and exact text offsets; the viewer response exposes neighbouring source segments without moving the core workspace.
- Job stages are completed facts, not simulated percentages. The local worker parses uploaded text, creates profile-matched candidates, and prepares local retrieval state in the background.
- Negative feedback can include answer/artifact/document/citation context. At three negative items the API emits a `START_RETUNE` signal; re-tuning is a separate, explicit action.

## Intentional MVP boundaries

- SQLite snapshot persistence is local-process durability, not a multi-worker production database.
- The local worker uses deterministic text parsing, candidate-specific chunking, and lexical retrieval; replace it with a managed queue and provider-backed embedding/vector pipeline without changing the HTTP shape.
- Retrieval is lexical mock scoring rather than embeddings. `embedding_model` is still persisted at instance scope to enforce the production invariant.
