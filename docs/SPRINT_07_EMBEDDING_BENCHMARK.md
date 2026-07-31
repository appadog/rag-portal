# Sprint 07 — 임베딩 Benchmark Foundation

> 상태: 구현·자동 QA 완료 / 실제 모델 smoke test 대기

## 목표

같은 golden corpus와 질문으로 BGE-M3, Qwen3-Embedding-0.6B, EmbeddingGemma-300M의 검색 품질을 재현 가능하게 비교한다. 모델 endpoint는 이미 구축되어 있다는 계약으로 호출하며, 로컬 CI의 fallback 결과는 `FALLBACK`으로 명시한다.

## 구현

- `POST /api/v1/embedding-benchmarks/run`: versioned golden corpus v1(3문서·3질문)을 각 모델로 실행하고 Recall@1, Recall@5, MRR, 평균 지연시간, vector dimension, provider를 저장한다.
- `GET /api/v1/embedding-benchmarks/latest`: 가장 최근 저장 결과를 반환한다. 실행 전에는 404 `BENCHMARK_NOT_RUN`을 반환한다.
- 결과는 SQLite snapshot에 저장·복원된다.
- 생성 화면은 결과가 있을 때만 실측 지표를 보여 주며, 없거나 실패한 경우 점수를 만들지 않는다.

## 검증

- Backend pytest: benchmark 실행·최신 결과 조회 계약 포함 통과.
- Frontend Vitest: 실측 결과 렌더링과 빈 상태 포함 통과.
- 실제 모델 smoke: 각 endpoint가 `local-tei` provider와 기대 dimension을 반환하는지 개발 서버에서 별도 확인한다.

## UX 기준

상세 상태·지표 위계·접근성 기준은 [Sprint 07 benchmark UX 검토](./design/SPRINT_07_BENCHMARK_REVIEW.md)를 따른다. 최고 점수 모델은 기존 지식 공간의 모델을 자동 변경하지 않으며, 사용자는 실측 결과를 근거로 다음 생성에서 선택한다.

## 다음 입력

Sprint 08은 이 benchmark 결과와 후보 상태 계약을 이용해 500 chunks 이상 문서의 샘플 비교와 확정 뒤 전체 재인덱싱을 구현한다.
