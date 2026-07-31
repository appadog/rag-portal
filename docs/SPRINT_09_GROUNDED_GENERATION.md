# Sprint 09 — Grounded generation and streaming

## Outcome

Search and tuning comparison now share one grounded-generation boundary. The local generator receives the user question and only the retrieved source contexts. It must return sentence-level source IDs. The API validates every generated sentence before exposing it; a failed endpoint or an invalid citation response becomes an explicit extractive fallback, never ungrounded model text.

## Local generator contract

Configure `RAG_GENERATOR_URL` (and optionally `RAG_GENERATOR_MODEL`). The service is assumed to be available in the model-ready development environment and exposes:

```text
POST {RAG_GENERATOR_URL}/generate
```

Request body:

```json
{
  "question": "국내 출장 숙박비 한도는?",
  "contexts": [
    {"segment_id": "segment-uuid", "text": "국내 출장 숙박비는 1박 10만원을 한도로 합니다."}
  ],
  "response_schema": {
    "sentences": [{"text": "string", "citation_ids": ["segment_id"]}]
  }
}
```

The endpoint response must contain a non-empty `sentences` array. Each sentence must have non-empty `text` and `citation_ids`. The generator is not given the complete document, prior generated answers, or arbitrary source data.

## Grounding validation and fallback

The API rejects a model result when a sentence has no citation or references any ID outside the supplied retrieved segment IDs. The user then receives a sentence copied from the retrieved segment, an inline citation, and:

```json
{
  "generation": {
    "mode": "EXTRACTIVE_FALLBACK",
    "provider": "extractive-fallback",
    "fallback": true,
    "fallback_reason": "INVALID_GROUNDING",
    "grounding_valid": true
  }
}
```

Endpoint failures use `fallback_reason: "GENERATOR_UNAVAILABLE"`. When retrieval has no acceptable evidence, generation is not attempted and the pre-existing “관련 문서를 찾지 못했습니다” response carries `mode: "NOT_ATTEMPTED"`.

## API and streaming

- `POST /api/v1/rag-instances/{id}/search` now returns `generation` metadata in addition to the existing answer, citations, grounding, retrieval, and artifact fields.
- `POST /api/v1/rag-instances/{id}/tuning/compare` returns the same metadata per comparison candidate. Its `TUNING_COMPARISON` artifact summarizes providers, fallback count, and grounding validation.
- `GET /api/v1/rag-instances/{id}/search/stream` preserves the existing `citations` and `token` events. Token data adds a monotonic `index`; `done` adds `generation`, so clients can show a quiet fallback/status explanation without parsing answer text.
- `ANSWER` artifacts persist the generation provider/model/fallback/grounding fields in both metadata and payload.

The selected search answer retains only the citations used to validate that generated answer; citations from unrelated retrieved documents are not appended after generation.

## Runtime assumption

`generator-grounded` is now part of an instance execution plan and appears in `GET /api/v1/model-runtime`. A model-ready environment therefore needs a reachable local generator endpoint as well as the selected embedding/reranker services. The fallback is for local-development resilience and must remain visibly labeled; it is not a model-quality equivalent.

## Automated verification

Executed on 2026-07-31:

```text
cd apps/backend && .venv/bin/pytest -q
22 passed
```

Tests monkeypatch the generator to confirm that only `{segment_id, text}` retrieval contexts are passed, that model-provided citations are persisted in answer artifacts, that invalid citation IDs never leak model text, and that SSE emits `citations`, token events, and explicit fallback metadata in `done`.
