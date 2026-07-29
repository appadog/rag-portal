# RAG Portal MVP product decisions

## Product outcome

Enable a non-technical user to create a trusted, document-grounded RAG workspace without learning parsing, chunking, embeddings, or retrieval terminology.

## Release scope

1. Create a workspace and answer a short setup questionnaire.
2. Upload a document; parsing and candidate-pipeline preparation start automatically.
3. Ask natural-language comparison questions and choose one or more helpful results.
4. Require a single leading candidate before final confirmation.
5. Search the completed workspace, with visible inline evidence and source scope selection.

## Decisions made for the MVP

| Area | Decision | Why |
| --- | --- | --- |
| Authentication | Assume the user is already signed in. | Keeps the first release focused on the RAG workflow. |
| Language | Korean-first interface; technical terms are progressively disclosed. | The target user is a Korean non-specialist. |
| Embedding selection | One embedding model per workspace, selected via a short questionnaire. | Mixing vector spaces across documents would break integrated retrieval. |
| Pipeline selection | Per-document candidate pipelines; compare answers, not opaque scores. | Users can judge usefulness from grounded answers. |
| Retrieval language | Use friendly labels such as `일반 검색` and `정밀 검색`, with explanations on demand. | Avoids forcing users to understand hybrid/reranking terminology. |
| Trust | Do not answer when evidence is insufficient; always expose the evidence used. | An unsupported fluent answer is worse than an explicit miss. |
| Long work | Preparation is an asynchronous, resumable job with polling-friendly progress. | Users can leave and return without losing work. |
| External AI | Provide a deterministic local/demo path; keep a provider seam for HF or production models. | The product remains runnable before credentials are supplied. |

## Acceptance journey

1. From the dashboard, create a workspace and select the recommended model.
2. Upload a text document and see processing move through parsing and candidate preparation.
3. Ask a question, compare candidate answers with their sources, and vote.
4. Break any tie, confirm the winning configuration, and land in the workspace.
5. Ask a search question, inspect the inline evidence, and leave optional feedback.

## Deferred decisions

- Production HF credential ownership and rate-limit policy.
- Golden-query authoring process for embedding benchmarks.
- Concrete retrieval thresholds and feedback-to-retuning threshold, to be calibrated with usage data.
- Real PDF/OCR, durable storage, and full-scale vector indexing.
