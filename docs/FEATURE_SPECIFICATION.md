# RAG Portal 기능 명세서

> 대상: 제품·프론트엔드·백엔드·QA 담당자  
> 기준: Sprint 01–15 구현·자동 QA 상태
> 로그인: 이미 완료된 세션을 전제로 하며, 인증·권한 관리는 이 명세 범위 밖이다.

## 1. 제품 목적

비전문가가 문서를 올리고, 문서 특성에 맞는 청킹·검색 후보의 **답변과 근거를 비교**해 파이프라인을 확정한 뒤, 근거가 연결된 검색을 사용하는 포털이다. 검색 결과는 제공된 문서 근거에 연결되어야 하며, 생성 모델이 준비되지 않았거나 검증에 실패하면 이를 숨기지 않고 발췌 기반 fallback으로 표시한다.

## 2. 화면과 사용자 흐름

| 경로 | 화면 | 제공 기능 |
| --- | --- | --- |
| `/rag` | 대시보드 | 지식 공간 목록, 처리·튜닝·준비 상태, 생성 진입 |
| `/rag/new` | 지식 공간 생성 | 질문지, 임베딩 모델 3종 추천·선택, 최근 benchmark 결과 |
| `/rag/:id/setup` | 문서 준비·후보 비교 | 파일 업로드, job 진행/취소/재시도, 후보 답변·근거 비교, 투표·확정 |
| `/rag/:id` | 검색 워크스페이스 | 문서 범위 선택, 질문·중단·재시도, 답변·인용·모델 실행 상태, 피드백·재튜닝 |
| `/guide` | 가이드 | RAG, 청킹, 검색 방식의 제품 내 설명 |

기본 흐름은 다음과 같다.

1. 질문지 결과를 바탕으로 임베딩 모델 하나를 지식 공간 단위로 고정한다.
2. TXT, PDF, DOCX, XLSX 또는 OCR 가능한 스캔 문서를 업로드한다.
3. 서버 job이 파싱·문서 분석·후보 생성·인덱싱을 수행한다.
4. 사용자는 동일 질문의 후보 답변과 인라인 인용을 비교하고 `READY` 후보에만 투표한다.
5. 단독 1위 후보를 문서별 파이프라인으로 확정한다. 대형 문서의 샘플 비교는 확정 뒤 전체 재인덱싱한다.
6. 확정 문서를 하나 이상 선택해 grounded 검색을 수행하고, 인용 원문·관련 artifact·피드백을 확인한다.
7. 원본 보관이 확인된 문서는 checksum·처리 버전을 확인한 뒤 명시적으로 재파싱할 수 있다. 재파싱은 이전 artifact를 지우지 않는다.
8. 재튜닝·후보 탐색은 추천과 근거를 보여주지만 자동 실행·자동 확정하지 않는다. 사용자가 시작하고 탐색 변경은 rollback/restore할 수 있다.

## 3. 기능 상세

### 3.1 지식 공간·모델 선택

- 한국어/온프레미스/예산/다중 홉 질문지를 사용해 `BGE-M3`, `Qwen3-Embedding-0.6B`, `EmbeddingGemma-300M`을 설명 가능한 이유와 함께 추천한다.
- 선택 모델은 지식 공간 전체에 고정한다. 문서별로 다른 embedding 공간을 섞지 않는다.
- benchmark는 Recall@1/5, MRR, 평균 지연시간, dimension, provider를 표시하지만 최고 점수 모델을 기존 공간에 자동 적용하지 않는다.

### 3.2 문서 처리·적응형 후보 생성

- PDF/DOCX/XLSX/TXT를 실제 파서로 추출한다. 스캔 PDF·이미지는 Tesseract가 준비된 경우 OCR을 사용한다.
- 문단·제목·표 비율·길이·OCR 여부를 분석하고 청킹 전략 3개와 파라미터를 계산한다.
- 각 청킹 전략에 Hybrid, Hybrid+Rerank, Dense 또는 BM25를 연결해 보통 9개 후보를 만든다.
- 후보는 자체 청크·벡터·모델 provider·파라미터·선택 근거를 저장한다.

### 3.3 job·후보 상태와 복구

job 상태는 `QUEUED`, `PARSING`, `GENERATING_CANDIDATES`, `INDEXING`, `SUCCEEDED`, `FAILED`, `CANCELLED`다. 취소와 재시도를 제공한다.

후보 상태는 아래처럼 job 상태와 구분한다.

| 상태 | 의미 | UI/행동 |
| --- | --- | --- |
| `PREPARING` | 후보 인덱스를 준비 중 | 대기, 선택 불가 |
| `READY` | 비교 가능한 후보 | 답변·근거 확인 후 선택 가능 |
| `FAILED` | 해당 후보 인덱싱 실패 | 원인 표시, job 재시도 가능 |
| `NO_EVIDENCE` | 준비는 됐지만 현재 질문의 근거 없음 | 질문/범위 변경 안내, 선택 불가 |

후보 일부가 실패해도 준비된 후보는 계속 비교할 수 있다. 실패 후보가 있으면 완료된 job도 전체 준비 재시도를 허용한다. 이 상태와 오류는 SQLite snapshot에 저장되어 새로고침·재시작 뒤 복원된다.

### 3.4 대형 문서 처리

- 기본 500 chunks 이상 문서는 `SAMPLE` 비교 범위를 사용한다. 임계값은 `RAG_PORTAL_COMPARISON_CHUNK_THRESHOLD`로 조정한다.
- 비교 화면은 샘플 이유, 예상 청크 수, 실제 비교 청크 수를 명시한다.
- 샘플 후보 확정 뒤 `FULL_REINDEX` job과 artifact를 생성한다.
- 전체 재인덱싱 진행 중에도 기존 확정 인덱스의 검색은 막지 않는다.

### 3.5 후보 비교·확정

- 답변 우선 카드에 인라인 citation과 원본 조각 보기 기능을 제공한다.
- `READY`이면서 근거가 있는 후보만 checkbox·투표·확정 대상이다.
- 복수 투표는 가능하지만 단독 1위일 때만 확정한다. 동점·선택 없음·준비된 후보 없음은 이유와 함께 완료를 비활성화한다.
- 모바일은 후보 전환기로 한 카드씩 집중해 본다. 증거 drawer와 confirm dialog는 Escape·focus 복원을 지원한다.

### 3.6 grounded 생성·검색

- 검색은 문서별 확정 retrieval 설정으로 후보를 가져온다.
- 다문서 검색은 문서별 점수를 정규화한 뒤 전역 병합하고, 필요한 경우 rerank top-k를 적용한다.
- generator에는 질문과 선택된 citation segment만 전달한다. 생성 문장의 citation ID가 제공 segment에 속하는지 검증한다.
- endpoint 실패 또는 잘못된 citation은 모델 문장을 버리고 extractive fallback을 반환한다. UI는 이를 `문서 근거 발췌 결과`로 작게 고지한다.
- SSE는 `citations` → `token` → `done` 이벤트를 보낸다. 사용자는 스트리밍을 중단할 수 있고, 부분 답변·요청 문서 범위·민감도는 보존된다.
- 다문서 답변은 문서별 citation 그룹과 문서 커버리지를 표시하며, 원시 점수는 기본 화면에 노출하지 않는다.

### 3.7 artifact·피드백·재튜닝·탐색

- 처리, 비교, 파이프라인 확정, 검색 답변, 재튜닝은 artifact로 저장한다.
- 답변 피드백에는 rating, comment, artifact/document/citation 문맥을 포함할 수 있다.
- 누적 부정 피드백은 명시적 재튜닝 추천 신호를 만들며, 재튜닝은 자동 실행하지 않고 사용자가 시작한다.
- 후보 탐색은 bounded 후보 풀·제안군·파라미터 변경 근거·evidence boundary를 ledger와 artifact로 남긴다. 제안 후보도 자동 투표·선택·확정하지 않는다.

### 3.8 원본 재현성·운영 작업

- 문서 원본은 SHA-256 checksum과 인스턴스 범위 dedup 상태를 가진 immutable source storage adapter에 보관한다. local filesystem이 기본이며 object storage gateway는 환경 설정으로 연결한다.
- parser revision, chunking analysis/version, embedding model/provider/dimension을 문서 provenance로 저장한다. 재파싱은 원본이 있는 경우에만 허용하며 이전 artifact를 보존한다.
- job은 dispatch receipt·idempotency key·worker heartbeat·bounded retry/backoff를 저장한다. 실패 한도 초과 작업은 dead-letter가 되며 명시적 recovery로만 재개한다.

## 4. API 계약 요약

전체 OpenAPI는 `/api/v1/openapi.json`을 기준으로 한다. 주요 endpoint는 아래와 같다.

| 영역 | endpoint |
| --- | --- |
| Runtime/benchmark | `GET /model-runtime`, `GET /large-document-policy`, `POST /embedding-benchmarks/run`, `GET /embedding-benchmarks/latest` |
| 지식 공간 | `GET/POST /rag-instances`, `POST /rag-instances/embedding-recommendations`, `GET /rag-instances/{id}`, `GET /rag-instances/{id}/execution-plan` |
| 문서/job | `POST /rag-instances/{id}/documents`, `POST /rag-instances/{id}/documents/{documentId}/reparse`, `GET /rag-jobs/{jobId}`, `POST /rag-jobs/{jobId}/cancel`, `POST /rag-jobs/{jobId}/retry`, job platform/dead-letter/recovery endpoints |
| 튜닝 | `POST /rag-instances/{id}/tuning/compare`, `POST /tuning-rounds/{id}/vote`, `POST /rag-instances/{id}/tuning/finalize` |
| 검색 | `GET /rag-instances/{id}/search/preflight`, `POST /rag-instances/{id}/search`, `GET /rag-instances/{id}/search/stream`, `GET /documents/{documentId}/segments/{segmentId}` |
| 운영 기능 | artifacts, feedback, retune recommendation, candidate exploration/rollback/restore, document delete endpoint는 OpenAPI와 backend README를 따른다. |

프론트 API adapter는 wire payload를 `apps/frontend/src/shared/api/client.ts`에서 타입으로 변환한다. API를 변경할 때 backend 응답, frontend adapter/types, mock fixture, backend pytest, frontend Vitest를 함께 갱신한다.

## 5. 영속성·runtime 경계

- 인스턴스·문서·후보·job·비교 라운드·artifact·feedback·benchmark run·exploration ledger는 SQLite snapshot에 저장한다.
- source storage와 Redis/SQS-compatible job adapter, dead-letter/recovery 계약은 구현됐다. local filesystem/thread fallback이 기본이므로 실제 object storage·broker·multi-worker smoke는 운영 release gate다.
- 임베딩·reranker·generator·OCR endpoint는 개발 서버에 구축되어 있다는 계약으로 호출한다. endpoint가 없거나 실패하면 provider/warning/fallback metadata를 반환한다.
- 실제 모델 없이 로컬 CI를 통과하는 것은 release gate 통과가 아니다. 실제 모델·실제 파일 E2E는 Sprint 11에서 수행한다.

## 6. 작업 인계 규칙

1. 다음 작업은 [`RAG_PORTAL_FEATURE_PLAN.md`](../RAG_PORTAL_FEATURE_PLAN.md)의 실제 runtime·운영 release gate부터 진행한다.
2. 각 Sprint는 `docs/SPRINT_XX_*.md`에 목적, API/상태 계약, 검증 결과, 외부 runtime 가정을 기록한다.
3. UI 변경은 NotebookLM-inspired design 문서와 접근성·반응형 회귀를 함께 검토한다.
4. 실제 모델 smoke 결과는 fallback 성공과 구분해 provider·실행 시각·corpus 버전을 남긴다.
5. `VITE_API_BASE_URL`이 설정된 실행에서는 API 오류를 mock fallback으로 숨기지 않는다. mock은 API base가 없는 프런트 단독 개발에서만 사용한다.

## 7. 참고 문서

- [개발 백로그와 스프린트 순서](../RAG_PORTAL_FEATURE_PLAN.md)
- [모델 runtime 구축 기준](./MODEL_RUNTIME_DEPLOYMENT.md)
- [백엔드 API 계약](../apps/backend/README.md)
- [Sprint 12 재튜닝](./SPRINT_12_FEEDBACK_RETUNING.md), [Sprint 13 재현성](./SPRINT_13_SOURCE_REPRODUCIBILITY.md), [Sprint 14 운영 job](./SPRINT_14_OPERATIONAL_JOBS.md), [Sprint 15 후보 탐색](./SPRINT_15_ADAPTIVE_EXPLORATION.md)
- [Sprint 07–15 backend QA](./SPRINT_07_15_BACKEND_QA.md), [frontend QA](./design/SPRINT_07_15_FRONTEND_QA.md), [UX QA](./design/SPRINT_07_15_UX_QA.md)
