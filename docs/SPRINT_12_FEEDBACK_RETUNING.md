# Sprint 12 — Feedback- and benchmark-informed retuning

## Outcome

Retuning recommendations are no longer a hidden fixed rule of three negative feedback items. `GET /api/v1/rag-instances/{id}/retuning-recommendation` now exposes a versioned, explainable decision record plus a live `baseline_snapshot` preview for currently finalized eligible documents. The existing feedback summary and feedback-post response retain `retuning_signal` for compatibility and add the same expanded recommendation inputs (without duplicating the baseline preview).

## Recommendation inputs

The current version is `2026-08-03.v1`. It exposes every input and threshold:

- Feedback counts, positive/negative totals, timestamp buckets, and a recency-weighted negative total: 1.0 for 0–14 days, 0.5 for 15–60 days, 0.25 after 60 days. The feedback trigger is `2.0` weighted negative feedback.
- Stored `ANSWER` artifact observations: ungrounded answers, extractive fallbacks, and grounded answers without stored citations. Two integrity events trigger a recommendation; one negative feedback plus one integrity event is also sufficient.
- The latest benchmark run's provider/status snapshot. `REAL_PROVIDER_EVIDENCE` and `NOT_RELEASE_EVIDENCE` are explicit, but Recall/MRR/latency are **not** converted into a retuning score. Fallback, failed, partial, or absent benchmarks produce runtime-review context only.

`recommendation_reasons` lists the rule(s) that fired. `BENCHMARK_NOT_QUALITY_EVIDENCE` may appear as a context reason without causing a recommendation. This keeps missing or fallback runtime evidence from pretending to be model quality.

## Baseline and comparable outcome artifacts

Before `POST /retune` removes the selected candidates, the service captures a `RETUNING_BASELINE` artifact containing:

- the prior finalized candidate configuration and comparison/full-reindex context for each requested document;
- the exact recommendation snapshot that prompted the action;
- capture timestamp and signal version.

The original retune response remains compatible and additionally returns `baseline_artifact` and `recommendation`. After the candidate preparation job succeeds, the next `POST /tuning/compare` for those documents creates `RETUNING_OUTCOME`. It stores the baseline, comparison question, candidate states, retrieval relevance, grounding/citation/fallback observations, and an explicit `PENDING_USER_VOTE` state.

These are comparable observations, not a claim that a new model or pipeline is better. Once a user votes and finalizes, the outcome records the selected pipeline and changes to `FINALIZED` (or `PARTIALLY_FINALIZED` for a multi-document retune). No automatic pipeline switch occurs.

## Persistence and API compatibility

Feedback, benchmark runs, the new recommendation inputs, and all artifact payloads use the existing SQLite snapshot. Existing clients can continue to read:

```json
{
  "retuning_signal": {
    "recommended": true,
    "negative_count": 2,
    "threshold": 2.0,
    "action": "START_RETUNE"
  }
}
```

`threshold` is retained as a numeric field but now means recency-weighted feedback, not a raw fixed count. New clients should use `version`, `threshold_details`, `inputs`, `recommendation_reasons`, and `runtime_review`.

## Verification

`apps/backend/tests/test_api.py` verifies a fallback benchmark is exposed as `NOT_RELEASE_EVIDENCE` and is not used in recommendation scoring; recency-weighted negative feedback triggers an explainable signal; and baseline/outcome artifacts survive the full retune → compare → vote → finalize flow.

```bash
cd apps/backend
.venv/bin/python -m pytest -q tests
```
