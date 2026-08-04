# Sprint 14 — Operational job adapters

## Goal

Keep the established job REST and SSE-facing state contract while making job
execution operable outside the development process. `PROCESSING`, `REPARSE`,
and `FULL_REINDEX` continue to expose their existing stages, artifacts, source
provenance, cancellation behavior, and polling endpoint.

## Durable job contract

Every `ProcessingJob` persists the following operational data in the SQLite
snapshot:

- `idempotency_key`, derived from the job kind, instance, documents, and
  artifact scope;
- dispatch backend, message receipt, and fallback reason;
- worker id, execution count, status, and last heartbeat;
- configured maximum attempts, backoff deadline, and dead-letter reason.

The runner takes a durable in-process claim before changing a job state.
Duplicate messages therefore return without rerunning work. Every stage
boundary updates a heartbeat, and the existing cancellation flag is checked at
the same boundaries. This keeps cancellation safe without changing the client
state machine.

## Dispatch and worker adapters

`RAG_QUEUE_BACKEND=thread` is the default and starts a local daemon worker.
It is intended for local development and test runs.

`RAG_QUEUE_BACKEND=redis` publishes a JSON list item to
`rag-portal:processing`; `RAG_QUEUE_BACKEND=sqs` publishes the equivalent
message to an SQS-compatible queue. Both messages contain only:

```json
{"job_id": "…", "idempotency_key": "…"}
```

A production Redis/SQS consumer must call:

```python
from app.main import consume_dispatched_job

consume_dispatched_job(job_id, idempotency_key)
```

The durable claim makes at-least-once delivery safe. If Redis/SQS is not
configured or cannot be reached, dispatch uses the local thread fallback and
records that fact on the job. The application does not require either external
service to start locally.

## Failure, retry, and recovery

`RAG_JOB_MAX_ATTEMPTS` defaults to `3`; `RAG_JOB_RETRY_BACKOFF_SECONDS`
defaults to `0`. A failed run receives `next_attempt_at`. Retry is rejected
until that time and after the attempt budget is exhausted. A job at its budget
is put in `DEAD_LETTER`, retaining its error and artifact provenance.

Operators use the following sequence after fixing the underlying issue:

1. Inspect `GET /api/v1/rag-jobs/dead-letters`.
2. Verify queue and worker health with `GET /api/v1/job-platform`.
3. Call `POST /api/v1/rag-jobs/{job_id}/recover`.

Recovery is explicit: it resets the retry budget and queues the original job
through the same adapter contract. It does not replace source objects, erase
existing artifacts, or invent a new provenance chain.

## Observability

`GET /api/v1/job-platform` returns requested/effective queue adapters,
readiness and fallback detail, local in-flight count, job-state totals,
dead-letter count, and the most recent worker heartbeats. Individual job
payloads expose the complete `operational` object while retaining the former
top-level fields for existing clients.
