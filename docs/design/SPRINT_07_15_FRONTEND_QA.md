# Sprint 07–15 frontend QA

Reviewed: 2026-08-03  
Scope: benchmark, large-document reindex, grounded search, multi-document evidence, retuning, source provenance/reparse, operational jobs, and adaptive exploration. Backend and top-level planning documents were not changed by this QA pass.

## Release result

The responsive/reparse/stop-language P0 findings and the stream-preflight/mock-fallback P1 findings were remediated and regression-tested. Formatting, type checking, all frontend tests, the production build, and whitespace validation pass. Sprint 15 also marks the actual proposed variant candidates, rather than their parent candidates, when the backend supplies both `narrowed_candidate_ids` and proposal `candidate_id` values. Repeated exploration rationales are deduplicated and capped so the panel remains scannable.

| Area | Result | Evidence |
| --- | --- | --- |
| Sprint 07 benchmark | Pass | Only backend-provided measured scores are rendered; unavailable data has an explicit empty state. |
| Sprint 08 reindex | Pass | Per-document full-reindex state blocks search for the affected selected sources and gives a retry path. |
| Sprint 09 grounded search | Pass | Stream and fallback states distinguish supported grounding from unavailable evidence without exposing internal errors. |
| Sprint 10 evidence | Pass | Citations are grouped by source and remain reachable from answer content. |
| Sprint 11 release/runtime gate | Pass with runtime gate | Service-state diagnostics are user-readable; final readiness still depends on a live API/runtime response. |
| Sprint 12 retuning | Pass | Measurement, fallback, and unavailable boundaries are visible before a candidate can be compared or finalized. |
| Sprint 13 provenance/reparse | Pass | Source metadata and reparse action/status are visible without presenting an object-storage key as a user URL. |
| Sprint 14 jobs | Pass | Job states, retry/cancel actions, and history use explicit status text and loading/empty handling. |
| Sprint 15 exploration | Pass after P1 fix | Proposal cards use generated proposal IDs, never auto-select a candidate, and expose rollback/restore capability honestly. |

## State, responsive, and accessibility audit

- The detail workspace keeps the primary task usable on narrow screens and moves auxiliary panels into labelled dialogs. Escape, focus return, and keyboard tab containment are covered by the workspace tests.
- Panel state now follows the breakpoint model: three panels at desktop, Context plus Work at 1024–1379px, and Work-only by default below 1024px. At drawer widths, opening one auxiliary panel closes the other.
- Candidate comparison supports a mobile candidate switcher and keyboard tab navigation. The selected candidate is not changed when an exploration proposal is created.
- Benchmark, evidence, retuning, provenance, reparse, job, and exploration surfaces have distinguishable loading, unavailable, empty, error, and retry states where the API contract provides one.
- Status changes are readable text, not color-only indicators. User-facing error copy maps internal failure codes to recovery guidance.
- Exploration's evidence boundary explicitly distinguishes measured, fallback, missing, and pending information; the interface never implies a generated proposal was evaluated or finalized automatically.

## Fixed issue

### P0 — Work could be covered at tablet widths

The previous initial state opened both side panels above 720px even though Output is a fixed drawer below 1380px and Context becomes a fixed drawer below 1024px. Initial and resize state is now breakpoint-aware: Output starts closed at 1024–1379px; both drawers start closed below 1024px; and tablet drawers are mutually exclusive. The regression test covers 1280px, a resize to 800px, and the two drawer toggles.

### P0 — reparse could retain an invalid search scope

Reparse now has a confirmation dialog with Cancel as the default focus. Once accepted, the affected document is immediately removed from selection and locally excluded from search, while other selected documents and the question draft remain intact. The workspace shows a persistent work banner and direct job-status action. The regression test proves the subsequent request contains only the remaining ready document.

### P0 — stop control implied a server cancellation

The control is now labelled `표시 중단`, and the active and interrupted status copy explicitly says only this screen's display is stopped while server work can continue. A true server-side `생성 중단` remains conditional on a cancellation/artifact API contract.

### P1 — exploration proposal marker could identify the wrong candidate

The candidate-exploration response contains parent IDs in `narrowed_candidate_ids`, while generated proposal variants are supplied in `proposed[].candidate_id`. The previous mapper preferred the former, so a parent card could be labelled as a proposal even though the proposed variant was a different candidate. The mapper now prefers the proposal IDs and uses narrowed IDs only as a compatibility fallback. It also combines and deduplicates the two supported rationale fields.

Affected file: `apps/frontend/src/shared/api/client.ts`.

### P1 — stream preflight now exposes per-document conflicts before EventSource

`streamAnswer()` calls `GET /api/v1/rag-instances/{id}/search/preflight?document_ids=...` before creating `EventSource`. A response with `eligible: false` is converted into a typed `SearchPreflightError` using its `conflicts` document IDs and codes (`DOCUMENT_NOT_FOUND`, `DOCUMENT_NOT_FINALIZED`, `FULL_REINDEX_PENDING`, or `FULL_REINDEX_FAILED`). The workspace names the affected document, shows the server's recovery message, and provides a `문서 선택 조정하기` action that opens and focuses its checkbox. A `404` or `405` preflight response is the sole compatibility exception: the stream continues for an older server and retains its existing generic stream-error handling.

### P1 — configured API failures no longer return mock or silent success data

The API client now has a single mock-mode guard. If `VITE_API_BASE_URL` is absent, development fixture fallbacks remain available. If it is set, all existing read and mutation fallback paths rethrow the original request error, including instance reads/creation/upload, recommendations/runtime data, jobs, comparison/finalization/voting, feedback/deletion, and exploration operations. This prevents production API faults from looking like successful mock work.

## Remaining release gates

### P2 — live-browser coverage is still needed

Component tests cover the rendered state and keyboard flows, but no Playwright/axe run against a live backend was available. Release validation should exercise a real reindex conflict, SSE failure, reparse result, job retry/cancel, and exploration rollback/restore at both narrow and desktop viewports.

## Verification

Executed from `apps/frontend`:

```text
npm run format:check
npm test -- --run
npm run build
```

Executed from the repository root:

```text
git diff --check
```

All commands completed successfully. The test run contains 6 test files and 31 tests. There is no separate `lint` package script; `npm run build` runs `tsc -b` before Vite's production build. React Router emits its existing v7 future-flag warnings during tests, but they do not fail the suite.
