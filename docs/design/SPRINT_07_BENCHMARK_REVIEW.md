# Sprint 07 — 임베딩 벤치마크 패널 UX 핸드오프

> 대상: RAG Portal의 “우리 문서 실측 결과” 패널
>
> 원칙: 모델의 유명세나 공개 리더보드보다 **같은 문서·같은 질문·같은 검색 조건에서 실제로 근거를 찾았는지**를 먼저 보여 준다. AI 결과와 측정의 한계는 숨기지 않는다.

## 1. 패널의 역할과 정보 위계

벤치마크는 사용자가 매 질문마다 실행하는 기능이 아니라, 프로젝트의 모델 선택 근거를 축적하는 **저장 가능한 실행 결과(run)** 이다. `RagPortalPage`의 임베딩 모델 안내 안에서 아래 순서를 지킨다.

1. **이번 측정이 답하는 질문**: `내 문서에서 어떤 모델이 정답 근거를 더 잘 찾았나요?`
2. **측정 조건**: 문서/청크/대표 질문 수/검색 조건/실행 시각.
3. **핵심 결과**: Recall@5를 첫 번째 비교 기준으로 한 모델 표.
4. **해석과 다음 행동**: 현재 설정과의 관계, 다시 측정 또는 대표 질문 보완.
5. **참고 데이터**: 공개 벤치마크는 분리된 접힘 영역에 출처·조회일과 함께 표시한다. 실측 결과 표와 같은 순위로 섞지 않는다.

카드를 겹겹이 쌓지 않는다. 패널 header, 조건 요약 strip, 결과 table, 설명/행동 영역의 네 surface면 충분하다.

```text
[우리 문서 실측 결과]  마지막 실행: 2026. 7. 31. 14:20   [새 측정]
문서 3개 · 청크 248개 · 대표 질문 24개 · 고정 청킹/검색 조건  [측정 조건]

이번 문서에서는 BGE-M3가 정답 근거를 가장 자주 찾았습니다.  [결과 해석]

모델                 정답 근거 찾기   응답 속도   저장 크기  상태
BGE-M3  현재 사용 중       21/24 (87.5%)   420ms      1024차원  완료
Qwen3…  이번 측정의 우선 검토 20/24 (83.3%)  260ms      1024차원  완료
...
```

## 2. 상태별 UX

| 상태 | Header/상태 문구 | 본문 | Primary 행동 | 주의 |
|---|---|---|---|---|
| Empty — 대표 질문 없음 | `아직 측정할 질문이 없어요` | `문서에서 답을 확인하고 싶은 대표 질문과 정답 근거를 준비하면 모델을 비교할 수 있어요.` | `대표 질문 준비하기` | 실행 버튼만 disabled로 두지 않는다. |
| Empty — 문서/청크 없음 | `먼저 비교할 문서를 준비해 주세요` | `파싱된 문서와 청크가 있어야 같은 조건에서 모델을 비교할 수 있어요.` | `문서 확인하기` | 업로드 완료와 청크 준비 완료를 혼동하지 않는다. |
| Empty — 준비 완료 | `측정할 준비가 됐어요` | `문서 3개, 청크 248개, 대표 질문 24개를 같은 조건으로 비교합니다.` | `측정 시작하기` | 실행 조건과 예상 범위를 CTA 앞에 표시한다. |
| Running | `모델별로 정답 근거를 찾고 있어요` | 완료 모델 결과는 즉시 table에 표시하고, 남은 모델은 동일 높이 skeleton row로 유지한다. | `대시보드로 돌아가기` 또는 `실행 상태 보기` | fake % 금지. 실제 `완료 2/5개`와 현재 모델/재시도 원인을 표시한다. |
| Complete | `측정이 완료됐어요` | 핵심 결과 + 전체 결과 table + 조건/한계 | `새 측정 시작하기` | “절대 최고 모델” 같은 확정적 표현을 쓰지 않는다. |
| Partial model failure | `3개 모델 결과를 확인할 수 있어요 · 2개는 준비하지 못했어요` | 성공 결과 table을 유지하고 실패 모델은 별도 status row로 남긴다. | `실패한 모델 다시 측정하기` | 성공 모델을 감추거나 run 전체를 error page로 바꾸지 않는다. |
| Run failure | `이번 측정을 완료하지 못했어요` | 실행 조건·마지막 진행 단계·보존되는 이전 결과를 설명한다. | `다시 측정하기` | 이전 완료 run이 있다면 그대로 읽을 수 있어야 한다. |

### Running 상태의 고정 geometry

- 결과 table의 model row 순서와 높이는 실행 전부터 고정한다. 완료된 모델을 위로 재정렬하지 않는다.
- 각 row는 `대기`, `측정 중`, `완료`, `실패` icon+text를 갖는다. 모델별 latency/recall이 아직 없으면 dash 대신 `측정 중`을 표기한다.
- live region은 `5개 모델 중 2개 측정 완료`처럼 **완료 수 변경 시 한 번만** 알린다. query마다/토큰마다 낭독하지 않는다.
- 사용자는 작업을 떠날 수 있다. dashboard/패널 재방문 시 run ID로 현재 상태를 재조회한다.

## 3. 결과 hierarchy와 지표 설명

### 3.1 table 기본 열

| 순서 | 열 | 표시 규칙 |
|---|---|---|
| 1 | 모델 | 이해하기 쉬운 모델명 + 필요 시 모델 ID를 작은 보조 텍스트로 표시 |
| 2 | 정답 근거 찾기 | **primary: Recall@5**. `21/24 · 87.5%`처럼 분자/분모와 비율을 함께 표시 |
| 3 | 더 넓게 찾기 | Recall@10. 기본은 compact한 보조 열이며 small viewport에서는 details로 이동 |
| 4 | 응답 속도 | 평균 latency를 `420ms`로 표시. 동일 run 안에서만 비교 가능한 보조 지표 |
| 5 | 저장 크기 | 벡터 차원 또는 추정 index 크기. 높고 낮음에 품질 판단 색상을 쓰지 않는다 |
| 6 | 상태 | 완료/측정 중/실패 및 retry action |

table은 Recall@5 내림차순으로 sort하되, “현재 사용 중” 행은 pin/label로만 구분하고 순위를 왜곡하지 않는다. 동률은 같은 순위로 보이며 latency가 자동 tie-breaker가 되지 않는다.

### 3.2 쉬운 설명 문구

| 지표 | 화면 도움말 |
|---|---|
| 정답 근거 찾기 (Recall@5) | `대표 질문마다 정답 근거가 검색 결과 상위 5개 안에 있었는지 본 비율이에요. 높을수록 이 문서에서 근거를 놓치지 않았어요.` |
| 더 넓게 찾기 (Recall@10) | `상위 10개까지 넓혀 보면 정답 근거를 얼마나 찾는지 보여 줘요. 답변이 더 정확하다는 뜻은 아니에요.` |
| 응답 속도 | `질문 하나를 처리하는 데 걸린 평균 시간이에요. 실행 환경과 서비스 상태에 따라 달라질 수 있어요.` |
| 저장 크기 | `문서를 저장할 때 필요한 벡터 정보의 규모예요. 작다고 검색 품질이 더 좋은 것은 아니에요.` |

도움말은 hover만이 아니라 keyboard focus와 touch에서 열리는 popover로 제공한다. 단, primary metric의 의미는 표 위 설명에도 한 문장으로 항상 보인다.

### 3.3 비교 가능 조건

결과 table 위에는 다음 조건을 한 줄로 항상 표시한다.

`문서 3개 · 청크 248개 · 대표 질문 24개 · 고정 청킹: 현재 SourceSegment · 검색: 벡터 top-10 · 2026. 7. 31 실행`

- 문서, 대표 질문, 고정 청킹, 검색 조건 중 하나라도 다른 run은 trend/순위 비교에서 같은 그룹으로 섞지 않는다.
- 변경된 run에는 `비교 조건이 달라요` badge와 `이 결과는 이전 실행과 직접 비교할 수 없어요.`를 표시한다.
- 대표 질문이 너무 적은 run에는 `참고용 결과` badge와 `질문이 더 늘어나면 결과의 신뢰도가 높아져요.`를 표시한다. 정확한 최소 수는 backend/PM 정책으로 정하되 UI에서 임의의 신뢰 점수를 만들지 않는다.

## 4. 추천과의 관계

questionnaire의 추천은 언어·온프레미스·예산 같은 **프로젝트 시작 조건**으로 모델을 제안한다. 벤치마크는 그 선택을 우리 문서에서 검증하고, 향후 추천 로직의 근거 데이터를 축적한다. 둘을 같은 의미의 “추천”으로 취급하지 않는다.

| 상황 | 표시 | 사용자 행동 |
|---|---|---|
| 현재 사용 모델이 실측 1위 | `현재 설정이 이번 문서에서도 좋은 결과를 보였어요.` | 기본 유지. `측정 조건 보기` secondary |
| 다른 모델이 상위 | `이번 측정에서는 Qwen3-Embedding-0.6B가 더 자주 근거를 찾았어요.` | `변경 영향 보기` secondary. 자동 변경 금지 |
| 차이가 작거나 질문이 적음 | `결과 차이가 작아 한 모델을 단정하기 어려워요.` | `대표 질문 보완하기` |
| 부분 실패 | `완료된 모델만 비교한 결과예요.` | 실패 모델 재측정 |

- `이번 측정의 우선 검토`는 허용하지만, `가장 좋은 모델`, `권장 모델로 자동 변경`은 사용하지 않는다.
- 현재 인스턴스의 embedding model은 자동 변경하지 않는다. 변경은 벡터 공간/인덱스를 다시 만들어야 하므로, 별도 설정 흐름에서 `문서를 다시 인덱싱해야 해요`를 확인한 뒤 실행한다.
- 모델을 바꾸는 confirm에는 영향 범위(문서 수, 재인덱싱 필요, 기존 검색 중단 여부)와 `현재 설정 유지`를 먼저 둔다. 벤치마크 결과 화면의 primary CTA는 모델 변경이 아니라 **새 측정** 또는 **대표 질문 보완**이다.

## 5. 부분 실패·오류·재시도

1. API rate limit, model cold start, provider unavailable은 모델별 실패다. 실패한 모델 row에 `준비 실패`와 사용자용 원인(`모델 서비스가 응답하지 않았어요`)을 둔다.
2. raw HTTP code/stack trace는 `세부 정보`에만 둔다. 원인 없는 `실패`만 보여주지 않는다.
3. `실패한 모델 다시 측정하기`는 성공 모델을 다시 실행하지 않고 실패 model ID와 동일한 corpus/query/condition snapshot으로 새 attempt를 시작한다.
4. retry 중에는 해당 row만 `측정 중`으로 돌아가며 직전 실패 원인은 숨기지 말고 `이전 시도: …`로 보조 표시한다.
5. run 전체가 중단돼도, 이미 저장된 model result는 `이번 실행에서 확인된 결과`로 남긴다. 완료되지 않은 모델만 실패/미완료로 표시한다.
6. 사용자가 실행을 중단할 수 있는 정책이면 `측정 중단`은 secondary/danger-quiet action이고, 중단 후 가능한 결과와 다시 시작 방법을 명시한다.

## 6. 접근성

- 결과는 native `<table>`로 구현한다. caption에 run의 범위와 측정일을 넣고, column header는 `scope=col`을 갖는다.
- 정렬 가능 열에는 현재 정렬을 `aria-sort`로 알리고, keyboard로 정렬할 수 있게 한다. 화면 폭이 좁아 열을 details로 옮겨도 모델/Recall@5/상태는 항상 보인다.
- 상태는 success/progress/warning/danger token과 icon+text를 함께 쓴다. `측정 중` spinner만으로 의미를 전달하지 않는다.
- 실행/중단/retry button에는 `BGE-M3 측정 다시 시도`처럼 대상 모델/run이 포함된 accessible name을 사용한다.
- running summary만 `role=status`/`aria-live=polite`로 쓴다. table cell 값 변화·skeleton·progress animation은 live region에 넣지 않는다.
- popover, condition details, model change confirm은 Escape로 닫히고 focus를 trigger에 복원한다. confirm은 `aria-modal`, focus trap, 첫 focus=`현재 설정 유지`를 갖는다.
- 일반 텍스트 4.5:1, table border/interactive boundary 3:1을 지킨다. reduced motion에서는 spinner/skeleton shimmer를 정지한다.

## 7. 최소 API/UI 계약

```ts
type BenchmarkRunState = 'EMPTY' | 'QUEUED' | 'RUNNING' | 'PARTIAL' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
type BenchmarkModelState = 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

type BenchmarkRunView = {
  id: string;
  state: BenchmarkRunState;
  corpusLabel: string;
  documentCount: number;
  chunkCount: number;
  queryCount: number;
  fixedChunkingLabel: string;
  retrievalConfig: string;
  startedAt?: string;
  completedAt?: string;
  comparabilityKey: string;
  results: Array<{
    modelId: string;
    displayName: string;
    state: BenchmarkModelState;
    recallAt5?: number;
    recallAt10?: number;
    answeredQueryCount?: number;
    avgLatencyMs?: number;
    dimension?: number;
    failureMessage?: string;
    retryable: boolean;
  }>;
};
```

- `comparabilityKey`는 문서/대표 질문/청킹/검색 조건을 식별한다. 프론트가 서로 다른 run의 값을 억지로 trend 비교하지 않는다.
- result state와 metric null은 별개다. `0%`는 측정값이고, `측정 중`/`실패`는 metric 부재다.
- 공개 benchmark 참고값은 별도 `isReferenceScore`, `sourceUrl`, `accessedAt`으로 제공하며 실측 run result와 동일 객체/정렬에 섞지 않는다.

## 8. Sprint 07 acceptance checklist

- [ ] Empty는 질문 없음/문서·청크 없음/실행 가능 원인을 구분하고 다음 행동을 제공한다.
- [ ] Running은 실제 model 완료 수·현재 단계·재시도 이유를 보여 주며, 완료된 row를 즉시 유지한다.
- [ ] Complete table은 모델, Recall@5 분자/분모·비율, latency, dimension, 상태를 표시하고 Recall@5를 primary로 둔다.
- [ ] Partial은 완료 결과를 보존하며 실패 모델별 원인·retry만 표시한다. 전역 error page가 되지 않는다.
- [ ] metric 도움말은 Recall@5/10, latency, dimension의 의미와 한계를 설명하며 hover-only가 아니다.
- [ ] 현재 사용 모델, questionnaire 추천, 이번 실측의 우선 검토가 서로 다른 label/행동으로 표현된다.
- [ ] benchmark 1위가 현재 모델을 자동으로 바꾸지 않으며, 변경 흐름에는 재인덱싱 영향 확인이 있다.
- [ ] 비교 조건이 다른 run에는 비교 불가 notice가 있고, 공개 benchmark는 실측 결과와 분리된다.
- [ ] table, status, retry, tooltip/popover, confirm은 keyboard와 screen reader로 완결된다.
- [ ] 1440/1024/390px에서 핵심 열(모델·Recall@5·상태)과 주요 CTA가 가로 스크롤 없이 보인다.
