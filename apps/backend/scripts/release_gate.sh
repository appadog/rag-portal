#!/usr/bin/env bash
# Run against provisioned local model services. This intentionally refuses the
# ordinary local fallback path; use a fresh SQLite file for each evidence run.
set -euo pipefail

: "${RAG_PORTAL_DB_PATH:?Set an isolated SQLite path for this release-gate run}"
: "${RAG_EMBEDDING_URL_BGE_M3:?Set the BGE-M3 TEI endpoint}"
: "${RAG_EMBEDDING_URL_QWEN3_EMBEDDING_0_6B:?Set the Qwen TEI endpoint}"
: "${RAG_EMBEDDING_URL_EMBEDDINGGEMMA_300M:?Set the EmbeddingGemma TEI endpoint}"
: "${RAG_RERANKER_URL:?Set the reranker endpoint}"
: "${RAG_GENERATOR_URL:?Set the grounded generator endpoint}"

RAG_RELEASE_GATE=1 .venv/bin/python -m pytest -q tests/test_release_gate_e2e.py \
  --junitxml="${RAG_RELEASE_GATE_REPORT_PATH:-release-gate-junit.xml}"
