# Sprint 08 — Large-document comparison and full reindex

## Outcome

Large documents are now compared against a bounded, source-wide sample and are reindexed across the complete source only after a user selects one pipeline. The local implementation retains the original parsed source text and persists both comparison and reindex state through the existing SQLite snapshot.

## Policy

- Environment setting: `RAG_PORTAL_COMPARISON_CHUNK_THRESHOLD`
- Default: `500` chunks per chunking strategy
- Decision rule: when the largest estimated strategy count is greater than the threshold, a `RETUNE` upload uses `SAMPLE`; otherwise it uses `FULL`.
- Sampling: deterministic, evenly spaced source chunks. The first, middle ranges, and final range are represented rather than truncating only the beginning of a document.
- `REUSE` skips comparison and directly prepares a full index, even when the source is large.

The policy is discoverable via `GET /api/v1/large-document-policy`.

## Contract

### Upload and processing

`POST /api/v1/rag-instances/{id}/documents` retains the existing request shape. Its `decision` now includes:

```json
{
  "comparison_scope": "SAMPLE",
  "estimated_chunk_count": 741,
  "selected_chunk_count": 500,
  "comparison_plans": {
    "document-id": {
      "scope": "SAMPLE",
      "chunk_threshold": 500,
      "estimated_chunk_count": 741,
      "selected_chunk_count": 500,
      "candidate_chunk_counts": {"semantic": 321, "fixed": 741, "hierarchical": 104},
      "full_source_retained": true
    }
  }
}
```

For text uploads, this is calculated before the job is queued. For binary uploads it is recalculated after parsing; the authoritative plan is available through `GET /api/v1/rag-jobs/{jobId}` as `comparison_plans` and from the document detail. The processing artifact stores the same plan.

`GET /api/v1/rag-instances/{id}` exposes each document's `comparison` object plus `full_reindex` state. Candidate payloads retain their comparison scope, estimated chunk count, and selected chunk count; `chunk_count` is the currently indexed amount. `full_reindex` also declares `search_eligible`, `search_policy: "BLOCK_UNTIL_FULL_INDEX_SUCCEEDED"`, and `next_action` (`WAIT_FOR_FULL_REINDEX` or `RETRY_FULL_REINDEX`) so clients do not infer readiness from a stale candidate index.

### Finalization and full reindex

`POST /api/v1/rag-instances/{id}/tuning/finalize` keeps its existing response and adds:

```json
{
  "full_reindex": {
    "required": true,
    "job": {"id": "...", "kind": "FULL_REINDEX", "state": "QUEUED"},
    "artifact": {"id": "...", "type": "FULL_REINDEX", "status": "PROCESSING"}
  }
}
```

The job replaces the selected candidate's bounded index with chunks and vectors built from the full retained source. It has two visible stages: `FULL_CHUNKING` and `FULL_INDEXING`. It is persisted, resumes after process restart through the normal pending-job mechanism, and supports the existing cancel/retry endpoints. The chosen policy is strict: a sampled index is never searchable after finalization. Both `POST /search` and `GET /search/stream` return the same structured `409 FULL_REINDEX_PENDING` detail while work is active, or `409 FULL_REINDEX_FAILED` after failed/cancelled work, until the full index succeeds.

## Assumptions and boundaries

- The selected embedding model endpoint is assumed to be available according to the instance execution plan. The existing local fallback remains visible in provider metadata for developer use.
- This is a local SQLite snapshot and thread/Redis-adapter MVP, not a distributed exactly-once worker implementation.
- The 500 default is intentionally configurable; it remains a starting policy pending real per-strategy latency measurements.

## Automated verification

Executed on 2026-07-31:

```text
cd apps/backend && .venv/bin/pytest -q
20 passed
```

The Sprint 08 test sets the threshold to `3` and verifies sample selection, bounded candidate index sizes, finalization-created `FULL_REINDEX` job/artifact, completed full-sized selected index, and SQLite snapshot restoration of the new fields.
