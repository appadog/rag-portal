# Sprint 06 — 후보 준비 상태와 복구

> 상태: 구현·자동 QA 완료 / 실제 모델 smoke test 대기  
> 제품 백로그: [`RAG_PORTAL_FEATURE_PLAN.md`](../RAG_PORTAL_FEATURE_PLAN.md) §0.2 순서 1

## 목표

문서를 올린 뒤 각 청킹·검색 후보가 실제로 준비됐는지, 실패했는지, 질문에 근거가 없었는지를 사용자가 새로고침 뒤에도 이해하고 복구할 수 있게 한다.

이번 스프린트는 검색 품질을 바꾸지 않는다. 실제 임베딩·reranker·OCR endpoint는 개발 서버에 이미 기동되어 있다는 계약으로 호출하며, 서버를 새로 설치하거나 생성 모델을 붙이지 않는다.

## 상태 계약

| 상태 | 생성 위치 | 의미 | 사용자 행동 |
| --- | --- | --- | --- |
| `PREPARING` | 후보 인덱스 job | 청킹/벡터/인덱스를 준비 중 | 대기, job 진행 상태 확인 |
| `READY` | 후보 인덱스 완료 | 비교·투표 가능한 후보 | 답변·근거를 비교하고 선택 |
| `FAILED` | 후보 인덱스 실패 | 해당 후보는 준비되지 않음 | 실패 사유 확인, 문서 준비 job 재시도 |
| `NO_EVIDENCE` | 현재 비교 질문 결과 | 인덱스는 준비됐지만 이 질문의 근거를 찾지 못함 | 질문 또는 문서 범위를 바꾸고, 이 라운드에서는 선택하지 않음 |

`NO_EVIDENCE`는 인덱스의 영구 실패가 아니다. 비교 라운드·질문에 종속된 결과 상태이고, 후보의 준비 상태는 그대로 `READY`다.

## API 계약

### 후보 payload

```json
{
  "preparation": {
    "state": "READY",
    "ready": true,
    "error": null,
    "prepared_at": "2026-07-31T00:00:00+00:00"
  }
}
```

### 비교 result payload

```json
{
  "candidate": { "id": "…", "preparation": { "state": "READY" } },
  "candidate_state": "NO_EVIDENCE",
  "candidate_state_detail": "현재 질문을 뒷받침하는 근거를 찾지 못했습니다.",
  "citations": []
}
```

- 준비되지 않은 후보는 비교 결과에도 남겨 상태를 설명하되 답변·근거·투표 대상이 아니다.
- 투표 API는 `FAILED`, `PREPARING`, `NO_EVIDENCE` 후보를 422로 거절한다.
- 후보 상태와 라운드별 결과 상태는 SQLite snapshot에 저장해 재방문 시 복원한다.

## 작업 분담

| 역할 | 책임 | 산출물 |
| --- | --- | --- |
| PM/Backend | 상태 모델, snapshot migration, 비교·투표 제약, API 테스트 | backend contract·pytest |
| Frontend | 상태 카드, 비활성 선택, 실패/근거 없음 안내, 모바일 유지 | UI·Vitest |
| Designer/UX QA | 상태별 문구·위계·접근성 검토 | `docs/design/SPRINT_01_CANDIDATE_STATE_REVIEW.md` |
| QA | 새로고침·부분 실패·취소·재시도·근거 없음 회귀 확인 | test checklist 및 자동 테스트 |

## 완료 기준

- [x] 후보 payload와 comparison result가 상태·세부 이유를 반환한다.
- [x] 상태가 SQLite snapshot payload에 저장·복원된다.
- [x] 준비 실패·근거 없음 후보는 선택·투표·확정할 수 없다.
- [x] 모바일 후보 전환에서도 상태와 선택 가능 여부가 명확하다.
- [x] backend pytest, frontend Vitest/build, formatter를 통과한다.

## 구현 결과

- Backend는 후보별 `preparation_state`, 오류, 준비 완료 시각과 비교 라운드별 상태를 SQLite snapshot에 저장한다.
- 후보 일부의 인덱싱이 실패해도 준비된 후보는 비교할 수 있다. 실패 후보가 포함된 완료 job은 전체 준비를 다시 시도할 수 있으며, 재시도 시 관련 비교 라운드를 무효화한다.
- 비교 결과는 준비되지 않은 후보를 `FAILED`/`PREPARING`, 근거를 찾지 못한 준비 완료 후보를 `NO_EVIDENCE`로 구분한다. 투표 API도 같은 제약을 강제한다.
- Setup 화면은 상태 배지·설명·선택 불가 이유·준비됨 수·완료 불가 이유를 보여 준다. 실패 후보는 기존 job 재시도 행동으로 복구할 수 있다.
- 디자인 검토의 상세 수용 기준은 [`docs/design/SPRINT_06_CANDIDATE_STATE_REVIEW.md`](./design/SPRINT_06_CANDIDATE_STATE_REVIEW.md)에 남긴다.

## 자동 검증 기록

| 범위 | 결과 | 근거 |
| --- | --- | --- |
| Backend contract | 통과 | `pytest apps/backend/tests -q` — 17 passed. 후보 준비 완료·부분 실패·재시도·근거 없음 투표 거절을 포함한다. |
| Frontend UI | 통과 | `npm --prefix apps/frontend run test -- --run` — 13 tests. 상태별 비활성 선택, 실패 재시도, 준비/선택 수, 완료 불가 이유를 포함한다. |
| Build/format | 통과 | Prettier 및 `npm --prefix apps/frontend run build` |

## 다음 스프린트로 넘기는 입력

- 이 상태 계약을 사용해 실제 모델 runtime smoke test의 실패를 후보·job 단위로 보여 준다.
- Sprint 07은 golden corpus와 benchmark harness를 만들고 BGE-M3·Qwen3·EmbeddingGemma 호출 결과를 같은 계약으로 기록한다.

## 실제 모델 smoke test (환경 구축 뒤 실행)

1. `execution-plan`에서 embedding, reranker, OCR이 `READY`인지 확인한다.
2. TXT·PDF·스캔 PDF를 각각 업로드한다.
3. 후보 payload의 provider가 개발 fallback이 아닌 실제 runtime을 표시하는지 확인한다.
4. 고의로 하나의 모델 endpoint를 중지해 `FAILED` 후보와 job 재시도를 확인한다.

이 항목은 endpoint가 이미 구축되어 있다는 전제로 작성한 실행 체크리스트다. 로컬 CI에서는 network/model 없이 test double과 상태 계약만 검증한다.
