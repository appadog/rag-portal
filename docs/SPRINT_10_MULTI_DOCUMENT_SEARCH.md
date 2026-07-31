# Sprint 10 — Multi-document grounded search

## Goal

A search across finalized documents must respect the pipeline chosen for each source. It must not silently apply one document's retrieval configuration to every other document, and it must not pass an unbounded set of chunks to answer generation.

## Search contract

`POST /api/v1/rag-instances/{instance_id}/search` keeps the existing single-document behavior. When two or more finalized documents are selected, it now:

1. Retrieves independently from every finalized candidate using that candidate's `retrieval_config`. A request-level `retrieval_config` remains an explicit override and is recorded as such.
2. For `hybrid_rerank`, performs hybrid retrieval first, reranks only that document's top `RAG_MULTI_DOCUMENT_RERANK_TOP_K` entries (default `8`), then blends the base and reranker scores.
3. Normalizes each source independently by its maximum raw score (`per_document_max`) before the global merge. This prevents documents with different score distributions or chunk counts from dominating simply because their local scale is larger.
4. Orders all candidates by normalized score, source request order, then local rank. It selects at most `RAG_MULTI_DOCUMENT_CONTEXT_LIMIT` positive-score contexts (default `4`) for generation.
5. Sends only those selected `{segment_id, text}` values to the existing sentence-level grounded generator and validator.

The response retains `citations` for compatibility and adds `grouped_citations`, grouped by source document. Its `retrieval_metadata` contains the merge strategy, context cap, selected count, threshold, document candidate/configuration details, normalization input, rerank result, and globally ordered candidates. The same metadata and grouped citations are persisted in the `ANSWER` artifact payload. SSE `done` includes the grouped citations as well.

## Grounding and fallback

Every generated sentence must cite one or more supplied selected segment IDs. Unknown IDs, uncited sentences, or unavailable generation produce an `EXTRACTIVE_FALLBACK`. The fallback uses only the first two selected contexts and includes their citations; no model text is returned after a validation failure.

## Configuration

```dotenv
RAG_MULTI_DOCUMENT_CONTEXT_LIMIT=4
RAG_MULTI_DOCUMENT_RERANK_TOP_K=8
```

Invalid or non-positive values safely fall back to a minimum positive value/default behavior.

## Verification

`apps/backend/tests/test_api.py` covers two finalized documents with different configurations (`dense` and `hybrid_rerank`), verifies normalized global ordering, grouped cross-document citations, persisted artifact metadata, bounded context passed to generation, and invalid-generation fallback safety.

Run:

```bash
cd apps/backend
.venv/bin/python -m pytest -q tests/test_api.py
```
