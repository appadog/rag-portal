# Sprint 07–10 frontend audit

Reviewed: 2026-08-03  
Scope: benchmark, large-document comparison/reindex, grounded generation, and multi-document search UI/API adapter. Backend code was inspected only; no backend files were changed.

## Result

The frontend now represents the implemented Sprint 07–10 contracts without inventing benchmark scores, treating a sampled index as a completed one, or presenting an extractive fallback as generated prose. The responsive RAG workspace remains a single primary work surface on narrow screens and keeps keyboard paths for its drawers, tabs, and evidence panel.

| Sprint | UI/API evidence | Audit outcome |
| --- | --- | --- |
| 07 benchmark | `RagCreatePage` renders Recall@1, Recall@5, MRR, latency, provider, and dimension only when `GET /embedding-benchmarks/latest` returns a run. A missing/failed run shows an explicit no-score state. | Pass |
| 08 large documents | `instanceFromWire` reads the implemented nested `document.comparison` object (`scope`, estimated and selected chunk counts), so setup identifies sampled comparison as representative rather than complete. It also derives the pending `full_reindex` job exposed by document detail. | Pass, with runtime dependency below |
| 09 grounded generation | Search and SSE `done` map `generation.mode`, `fallback`, `fallback_reason`, and `grounding_valid`. The workspace uses plain-language fallback wording; internal codes such as `INVALID_GROUNDING` are not shown to users. | Pass |
| 10 multi-document search | Flat citations are enriched from `grouped_citations` and coverage is derived from those groups when legacy `document_coverage` is absent. The evidence panel can therefore preserve per-document provenance after SSE completion. | Pass |

## Correctness details

- Benchmark cards never use recommendation data as an observed result. The latest-run request is intentionally optional and the empty state says that no measurement has been run.
- Sample comparison names the affected document and shows selected/estimated representative chunks. The source remains distinguished from the later full reindex.
- The backend's implemented search contract returns `409 FULL_REINDEX_PENDING` while full reindex is incomplete. The detail header now says to wait before searching that document, instead of claiming the current search can still use the sampled index. The input remains available so users are not trapped in the screen; the server remains the authority for mixed-document eligibility.
- The post-finalization detail payload currently exposes `full_reindex` per document. The adapter uses the normal detailed job when available, otherwise exposes its id/state with an honest indeterminate-progress message rather than fabricating stage counts.
- Extractive fallback copy distinguishes invalid grounding from generator availability when the server supplies a reason. A backend-supplied human-readable `detail` takes precedence.
- Multi-document evidence buttons group citations by document id/name and open the corresponding evidence set. Search scope is snapshotted when a request starts, so a changing checkbox cannot rewrite the provenance of an in-flight answer.

## Responsive and accessibility evidence

- At narrow widths the work panel remains primary and context/output panels become mutually exclusive drawers; the controls expose `aria-expanded`, `aria-pressed`, and `aria-controls`.
- Escape returns focus from evidence to its citation trigger and also closes the relevant drawer/dialog.
- Output uses roving-arrow tab navigation with linked `tab`/`tabpanel` semantics. Document selection stays distinct from document management.
- Status changes (jobs, generation state, fallback metadata, and search scope) use concise status text rather than relying on colour alone.

## Focused verification

Executed from `apps/frontend` on 2026-08-03:

```text
npm test -- --run src/features/rag/RagDetailWorkspace.test.tsx src/features/rag/RagWorkspace.test.tsx
2 files passed, 15 tests passed

npm run build
tsc -b && vite build passed
```

The tests cover sampled-comparison disclosure, reindex-pending wording, fallback disclosure without leaking the internal reason code, multi-document source grouping/evidence navigation, mobile panel switching, focus restoration, search-scope locking, and tab keyboard navigation. React Router printed its existing v7 future-flag warnings; neither command failed.

## Remaining backend/runtime dependencies

- Sprint 07's current latest benchmark contract does not expose the richer run conditions, per-model completion lifecycle, or explicit confidence/quality context described in the UX review. The frontend can truthfully show the available metrics and no-score state; richer comparison table states require those fields from the API.
- A full-reindex document detail supplies `job_id` and state, but not necessarily a detailed job payload with stage progress. To show exact `FULL_CHUNKING`/`FULL_INDEXING` progress for every refresh, the detail endpoint must include that job payload or a stable job lookup must be available to the browser.
- The runtime needs reachable embedding, reranker (when selected), and `RAG_GENERATOR_URL` services. The fallback label makes development resilience visible, but it is not equivalent to a model-generated grounded answer.
- `EventSource` cannot reliably surface the JSON body of a pre-stream HTTP 409. The header prevents a false readiness claim; a structured preflight/stream-error event would let the composer present the server's exact reindex message before opening a stream.
