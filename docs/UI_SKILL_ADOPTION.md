# NotebookLM-inspired UI adoption

This is the product acceptance contract for the second RAG Portal iteration. It
applies the local `notebooklm-inspired-ui` skill without copying a third-party
product's visual identity.

## Product map

| Role | RAG Portal responsibility | Primary user outcome |
| --- | --- | --- |
| Context | Source documents, selected search scope, processing state | Know exactly what can influence an answer. |
| Work | Tuning comparison or grounded search composer and answer stream | Ask, compare, choose, and continue without losing context. |
| Output | Evidence reader, configured pipeline, jobs, feedback and re-tune signal | Verify a claim and act on the result. |

## Release acceptance criteria

- The desktop workspace makes selected sources visible while preserving the
  largest stable area for the active question and answer.
- The evidence viewer is reachable by mouse and keyboard, has a named control,
  moves focus to its title when opened, and restores focus when closed.
- Empty, loading, processing, error, no-evidence, and ready states communicate
  both status and the next valid action; disabled actions explain their
  prerequisite.
- At tablet width only the work area and one auxiliary panel compete for space;
  on mobile, source/evidence views become focused, reversible views rather than
  a shrunken three-column layout.
- Preparation jobs remain identifiable after navigation and show only backend
  supplied status/progress; no fabricated percentage is displayed.
- A document can be added using an existing finalized configuration or entered
  into its own re-tuning flow. Destructive removal requires confirmation.
- Searching without evidence visibly distinguishes a retrieval miss from a
  grounded answer.
- The keyboard-only happy path covers source selection, a query, citation open/
  close, and feedback.

## Non-goals for this iteration

- Pixel-copying NotebookLM or Google branding.
- Persisting server objects in the UI layout store.
- Introducing a vector database, real LLM provider, or authentication scope
  change merely for the UI iteration.
- Pretending a synchronous local mock has token-level streaming progress.
