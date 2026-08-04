# Sprint 13 — Source-file reproducibility

## Outcome

Every new JSON upload now persists an immutable original source before parsing. The existing `content` and `content_base64` request contract remains valid; no frontend multipart migration is required. The API records the exact source checksum and processing provenance needed to reproduce a parse/candidate run, and adds an explicit reparse workflow.

## Storage adapters

The default is `LocalFilesystemSourceStorage`:

```dotenv
RAG_SOURCE_STORAGE_BACKEND=local
RAG_SOURCE_STORAGE_PATH=.rag-sources
```

It stores immutable bytes at `instances/{instance-id}/sources/{sha256}`. A per-instance duplicate upload uses the same source object and reports `DEDUPLICATED` plus `deduplicated_from_document_id`; it still creates a separate document/candidate workflow. The policy is `REUSE_EXISTING_SOURCE_OBJECT`, not silent document deletion.

For deployed object storage, set `RAG_SOURCE_STORAGE_BACKEND=object` with:

```dotenv
RAG_OBJECT_STORAGE_ENDPOINT=https://object-gateway.internal
RAG_OBJECT_STORAGE_BUCKET=rag-portal-sources
RAG_OBJECT_STORAGE_TOKEN=...
```

The adapter uses an authenticated internal path-style gateway contract:

```text
PUT/GET {endpoint}/{bucket}/{key}
Authorization: Bearer {token}   # optional
```

`PUT` uses `If-None-Match: *`; `409`/`412` means the immutable key already exists. The application does not implement cloud-provider signing itself, so S3/MinIO deployments should expose that authenticated gateway or equivalent adapter configuration.

## Provenance contract

Document detail now exposes:

- `source`: SHA-256 checksum, byte size, storage backend/key, stored time, and instance-scoped dedup decision;
- `provenance.parser`: parser pipeline version, parser name, OCR use/warnings, parse revision, and timestamp;
- `provenance.chunking`: chunking pipeline version, profile/analysis, comparison scope and counts;
- `provenance.model`: selected embedding model, actual provider/dimension/warning, retrieval configurations, and index timestamp.

These fields are persisted in the existing SQLite snapshot alongside source-referencing documents. Legacy snapshots without a source key remain readable but cannot reparse; the API returns `409 SOURCE_PROVENANCE_UNAVAILABLE` and asks for a new upload rather than inventing source provenance.

## Reparse

```text
POST /api/v1/rag-instances/{instanceId}/documents/{documentId}/reparse
{"reason": "optional audit note"}
```

Before candidates are replaced, `REPARSE_BASELINE` captures the full prior document/provenance payload. `REPARSE_RUN` references that baseline and runs the normal `PARSING → CANDIDATES → INDEXING` stages with `job.kind: REPARSE`. It reads only the stored immutable source object, increments parser `parse_revision`, and retains all prior answer/decision/artifact records.

Reparse uses the existing job operations unchanged:

- `POST /rag-jobs/{jobId}/cancel` requests a safe stage-boundary cancellation;
- `POST /rag-jobs/{jobId}/retry` retries the same `REPARSE` job from its stored source;
- pending `REPARSE` jobs resume through the normal snapshot recovery dispatcher.

## Verification

`apps/backend/tests/test_api.py` verifies SHA-256 source reuse for two documents in one instance, persisted parser/chunking/model metadata, `REPARSE_BASELINE` and `REPARSE_RUN` history, parser revision increment, and cancel → retry behavior for a `REPARSE` job.

```bash
cd apps/backend
.venv/bin/python -m pytest -q tests
```
