# RAG Portal

비전문가가 문서를 올리고, 실제 검색 답변과 근거를 비교해 자신에게 맞는 RAG 파이프라인을 고를 수 있게 하는 제품입니다. 로그인은 이미 된 환경을 전제로 합니다.

## 현재 구현된 기능

| 영역 | 구현 내용 |
| --- | --- |
| 지식 공간 생성 | 짧은 질문지에 따라 임베딩 모델 3종을 추천하고, 사용자가 한 모델을 인스턴스 단위로 선택·고정합니다. |
| 문서 업로드·처리 | TXT, PDF, DOCX, XLSX를 실제 파서로 읽고, 스캔 PDF·이미지는 Tesseract OCR이 준비된 환경에서 처리합니다. 처리 상태는 비동기 job으로 조회·취소·재시도할 수 있습니다. |
| 적응형 청킹 | 문단, 제목, 표 형태, 길이, OCR 여부를 분석해 문서별 청킹 후보와 크기·오버랩·표 행 수 파라미터를 계산합니다. |
| 파이프라인 비교 | 문서마다 3개 청킹 × 3개 검색 방식(Hybrid, Hybrid + Rerank, 문서 특성별 Dense 또는 BM25)의 답변과 인라인 근거를 비교합니다. |
| 확정·검색 | 여러 후보에 투표할 수 있고 단독 1위만 확정합니다. 확정 뒤에는 근거가 있는 검색, 민감도 조절, 원문 인용 탐색을 제공합니다. |
| 운영 흐름 | 인스턴스·문서·후보·job·비교 결과·투표·산출물은 SQLite snapshot에 저장되어 재방문 뒤에도 복원됩니다. 피드백 누적 시 재튜닝 신호를 제공합니다. |
| 모델 계약 | 로컬 TEI 임베딩/reranker, OCR, Redis queue의 readiness와 인스턴스별 실행 계획을 API로 확인할 수 있습니다. |

## 사용자 흐름

1. 대시보드에서 지식 공간을 만들고, 추천된 임베딩 모델 중 하나를 선택합니다.
2. 문서를 업로드합니다. 시스템은 파일을 파싱하고 문서 구조를 분석한 뒤 처리 job을 즉시 반환합니다.
3. job이 완료되면 문서 특성에 맞춰 계산된 9개 후보의 답변·근거 조각을 같은 질문으로 비교합니다.
4. 좋은 답변을 낸 후보에 투표합니다. 동점이 아닌 단독 1위가 생기면 그 문서의 검색 파이프라인으로 확정합니다.
5. 확정된 문서만 실사용 검색에 포함됩니다. 답변의 인용을 열어 원문 위치와 앞뒤 조각을 확인할 수 있습니다.
6. 답변 또는 근거 품질이 좋지 않다고 피드백하면 누적 신호를 바탕으로 명시적인 재튜닝을 시작할 수 있습니다.

## 로컬 실행

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

## 실제 모델을 연결하는 실행 모드

기본 실행은 모델 endpoint가 없을 때 개발용 fallback을 기록하며 동작합니다. 실제 의미 검색과 모델 rerank를 검증하려면 선택한 TEI 임베딩 모델과 reranker를 별도로 기동해야 합니다.

```bash
cd apps/backend
cp .env.example .env
docker compose -f docker-compose.models.yml --profile bge --profile reranker up -d
.venv/bin/uvicorn app.main:app --env-file .env --port 8010
```

구현 범위와 실제 서버 구축 상태, 릴리스 체크리스트는 [모델 런타임 구축 기준서](docs/MODEL_RUNTIME_DEPLOYMENT.md)를 기준으로 합니다.

## 검증

```bash
cd apps/backend
.venv/bin/pytest -q

cd ../frontend
npm run format:check
npm test -- --run
npm run build
```

- Interactive API: [http://127.0.0.1:8010/docs](http://127.0.0.1:8010/docs)
- OpenAPI: [http://127.0.0.1:8010/api/v1/openapi.json](http://127.0.0.1:8010/api/v1/openapi.json)
- **기능 명세서·인계 문서:** [docs/FEATURE_SPECIFICATION.md](docs/FEATURE_SPECIFICATION.md)
- **개발 백로그·스프린트 순서:** [RAG_PORTAL_FEATURE_PLAN.md](RAG_PORTAL_FEATURE_PLAN.md)
- Backend contract: [apps/backend/README.md](apps/backend/README.md)
- Adaptive chunking policy: [docs/SPRINT_05_ADAPTIVE_CHUNKING.md](docs/SPRINT_05_ADAPTIVE_CHUNKING.md)
- Product decisions: [docs/PRODUCT_MVP_DECISIONS.md](docs/PRODUCT_MVP_DECISIONS.md)

## 현재 경계와 다음 운영 작업

- SQLite snapshot은 단일 프로세스 재시작을 위한 영속성이고, 다중 worker 운영용 데이터베이스는 아닙니다.
- 원본 이진 파일은 현재 SQLite snapshot에 보관하며, 운영 환경에서는 object storage로 옮겨야 합니다.
- Redis adapter는 구현되어 있으나 이 로컬 환경에는 Redis가 기동되어 있지 않습니다.
- 실제 로컬 모델 서버와 Tesseract도 아직 이 환경에 구축되지 않았습니다. API는 이 상태를 `NOT_CONFIGURED`, `UNAVAILABLE`, `NOT_INSTALLED`로 표시합니다.
