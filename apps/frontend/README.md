# RAG Portal Frontend

React + TypeScript + Vite + styled-components frontend for the RAG Portal MVP. It follows the backend contract in [`../backend/README.md`](../backend/README.md), with a functional mock fallback when `VITE_API_BASE_URL` is absent.

## Run

```bash
cd apps/frontend
npm install
npm run dev
```

To use the FastAPI service, create `.env.local`:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8010
```

## Screens and flow

- `/rag`: 10-second dashboard scan with state and progress badges.
- `/rag/new`: non-expert questionnaire, model recommendation, and instance creation.
- `/rag/:id/setup`: upload, persistent background preparation with polling, answer/evidence comparison, multiple votes, tie-safe final confirmation.
- `/rag/:id`: NotebookLM-inspired document scope + answer workspace; citation opens the original evidence and settings stay separate.

The client maps the backend's snake_case wire format into frontend view types in `src/shared/api/client.ts`. API failures intentionally use fixtures so design work can continue in parallel.

## Checks

```bash
npm run build
npm test
```

Known MVP limits: binary uploads currently travel as JSON base64 and should move to object storage in production; the local fallback is deliberately labelled when TEI embedding/reranker services are not provisioned; SQLite snapshot persistence is not a multi-worker production database. Job cancel/retry is implemented at safe processing-stage boundaries.
