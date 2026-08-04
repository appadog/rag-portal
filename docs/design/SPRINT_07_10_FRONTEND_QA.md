# Sprint 07–10 frontend regression QA

Reviewed: 2026-08-03  
Scope: embedding benchmark, sampled large-document comparison/full reindex, grounded REST/SSE answer delivery, and multi-document evidence. This follow-up is after the Sprint 11–15 implementation; no backend files or top-level planning documents were changed.

## Result

No reproducible P0 regression remains in the Sprint 07–10 frontend surface. The current workspace keeps the primary search task visible at supported widths, blocks known invalid reindex scopes, preflights stale scopes before opening SSE, and preserves document-specific evidence for both REST and stream responses.

| Area | Result | Current evidence |
| --- | --- | --- |
| Sprint 07 benchmark | Pass | Measured metrics render only from a latest benchmark response. A 404 means no run yet; configured API failures show an actionable error rather than fixture data. |
| Sprint 08 large document/reindex | Pass | Sample/full state maps from the nested document payload. Selected pending documents block search locally, while the GET preflight turns stale server conflicts into document-level recovery guidance. |
| Sprint 09 grounded answer | Pass | REST and SSE map generation/fallback metadata. The UI calls a display-only stop control and keeps partial safe text; internal grounding codes are not exposed. |
| Sprint 10 multi-document evidence | Pass | Grouped citation metadata enriches flat REST/SSE citations with document IDs and derives coverage when needed. Each grouped citation now loads its own source preview when selected. |

## Fixes made during this regression pass

### P1 — benchmark absence and benchmark/API failure were conflated after fallback hardening

With a configured API, the mock-fallback policy correctly rethrows request errors. That inadvertently made the valid latest-benchmark `404` (no measurement run yet) behave like an application failure. The client now treats only that endpoint's 404 as the intentional empty state. Other configured API failures remain errors, and the creation questionnaire stays available with an alert and retryable `후보 비교하기` action.

### P1 — selecting another citation did not load its own source

The Evidence panel initially loaded only the first citation in a grouped source. Selecting another citation changed its visible excerpt but did not request the corresponding source preview. Selection now loads the selected citation's `navigateUrl`, updates only that matching citation, and uses a semantic list containing accessible buttons.

## Responsive and accessibility audit

- Initial panel state is 3-panel at desktop, Context plus Work at 1024–1379px, and Work-only below 1024px. At drawer widths, Context and Output are mutually exclusive.
- Reindex-pending selections disable the question control with plain-language reason text. The preflight conflict action opens Context and focuses the affected checkbox.
- Output tabs retain linked `tab`/`tabpanel` semantics and arrow-key navigation. Evidence selection, Escape-close, and focus return are covered by tests.
- Fallback, missing benchmark, pending reindex, stream interruption, and evidence errors use text status or alerts rather than color-only signals.

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

All commands completed successfully. The suite has 6 test files and 35 tests. Focused coverage includes benchmark metrics/empty/error, reindex blocking and preflight recovery, REST/SSE fallback and grouped-citation mapping, multi-document Evidence navigation, and responsive/keyboard drawer behavior. React Router prints existing v7 future-flag warnings during tests without failing them.

## Remaining runtime gates

- Benchmark UI has no privileged run/re-run action. Production still needs a controlled benchmark execution workflow and versioned real-corpus evidence; the UI only presents the latest available result honestly.
- The browser suite uses test doubles. Before release, run real-provider E2E for sample → full reindex → preflight conflict/retry → grounded REST/SSE answer across 1440px, 1024px, and 390px viewports.
- SSE remains buffered replay under the current server contract. `표시 중단` is intentionally not presented as a server cancellation; a future cancellation/artifact contract must update both semantics and tests together.
