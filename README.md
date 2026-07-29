# RAG Portal

비전문가가 문서를 올리고, 실제 검색 답변을 비교해 자신에게 맞는 RAG 파이프라인을 고를 수 있게 하는 MVP입니다. 로그인은 이미 된 환경을 전제로 합니다.

## MVP flow

1. 간단한 질문으로 RAG 인스턴스와 인스턴스 단위 임베딩 모델을 만듭니다.
2. 문서를 올리면 파싱·후보 생성 작업을 조회 가능한 job으로 반환합니다.
3. 문서 특성별 3개 청킹 × 3개 검색 후보의 답변과 근거를 비교합니다.
4. 한 라운드에서 여러 후보에 투표할 수 있지만, 단독 1위가 될 때만 확정합니다.
5. 확정 후에는 근거가 있는 검색 답변, 인라인 인용, 검색 민감도, 선택 피드백을 제공합니다.

## Local runbook

Backend (terminal 1):

```bash
cd apps/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8010
```

Frontend (terminal 2):

```bash
cd apps/frontend
npm install
VITE_API_BASE_URL=http://127.0.0.1:8010 npm run dev
```

Frontend only mock mode remains available by omitting `VITE_API_BASE_URL`.

## Verify

```bash
cd apps/backend
.venv/bin/pytest -q
```

- Interactive API: [http://127.0.0.1:8010/docs](http://127.0.0.1:8010/docs)
- OpenAPI: [http://127.0.0.1:8010/api/v1/openapi.json](http://127.0.0.1:8010/api/v1/openapi.json)
- Backend contract: [apps/backend/README.md](apps/backend/README.md)
- Product decisions: [docs/PRODUCT_MVP_DECISIONS.md](docs/PRODUCT_MVP_DECISIONS.md)

## Current MVP boundary

The API persists data in memory and uses deterministic mock parsing/retrieval so it works locally without Docker, a vector database, an LLM key, or a background worker. Its HTTP job, comparison, citation, SSE, and finalization contracts are designed to remain stable when those production integrations are introduced.
