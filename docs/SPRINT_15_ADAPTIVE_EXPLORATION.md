# Sprint 15 — Adaptive candidate exploration

## Product rule

Adaptive exploration proposes bounded chunking/retrieval variants; it never
votes for, selects, finalizes, deletes, or changes a document's finalized
pipeline. The existing comparison → user vote → explicit finalize flow remains
the sole selection mechanism.

## API

- `POST /api/v1/rag-instances/{instance_id}/candidate-exploration`
- `GET /api/v1/rag-instances/{instance_id}/candidate-exploration`
- `GET /api/v1/candidate-exploration/{exploration_id}`
- `POST /api/v1/candidate-exploration/{exploration_id}/rollback`
- `POST /api/v1/candidate-exploration/{exploration_id}/restore`

Create requests accept document IDs, an optional comparison question, and a
bounded `max_proposals` (1–6). The response is deliberately named
`candidate_exploration` and contains `pool`, `proposed`, `rationale`, `ledger`,
and `rollback` for direct UI consumption.

## Signals and proposals

The round snapshots the current candidate pool and records only transparent,
bounded operational signals: index readiness, existing user vote count,
previous comparison evidence/no-evidence counts, and vector count. It derives
an internal *exploration priority* only to stay within the requested proposal
budget. It explicitly is not a quality score, a benchmark result, or a reason
to auto-select a pipeline.

For each narrowed candidate, the service creates one temporary variant with a
small strategy-specific chunking adjustment and one retrieval-mode change.
The resulting candidate is indexed using the existing model runtime and keeps
the parent candidate ID plus exploration round ID. It can then enter the normal
comparison/vote flow if the user chooses.

## Ledger, provenance, rollback

Rounds and their proposal specs are stored in the existing SQLite snapshot,
alongside a `ADAPTIVE_EXPLORATION` artifact. The artifact captures source,
parser, chunking, and model provenance without replacing prior source or
retuning artifacts.

Rollback archives only candidates created by that exploration and removes them
from active candidate lists; it does not touch the original pool, votes,
comparisons, finalized candidates, or source objects. Restore reactivates the
same candidates (or recreates one only if it has been removed independently),
then records the event in the immutable-style ledger. Both actions are explicit
operator/user actions and never finalize a candidate.

## UI guidance

Present the proposed variants as optional comparison inputs. Show their parent,
parameter/retrieval deltas, readiness, reasons, and the ledger. Keep the
existing explicit vote and finalize controls visible; a `PROPOSED` or
`RESTORED` exploration is not a recommendation to finalize.
