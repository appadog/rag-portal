# Sprint 07–10 UX/QA 재감사 — S11–15 반영 후 남은 공백

> 감사일: 2026-08-03  
> 범위: benchmark, sample/full reindex, grounded chat/SSE, 다문서 근거, breakpoint·접근성  
> 기준: NotebookLM-inspired **Context → Work → Output**, Visible System Status, Verification Is First-Class, No Invisible Prerequisites

## 결론

S11–15 변경으로 이전 Sprint 07–10 감사의 중요한 UI 공백 두 개가 해소됐다.

- sample 비교에서 전체 색인이 끝나지 않은 문서는 Context에서 상태를 보이고, 검색 입력을 막거나 선택 해제로 복구한다. 또한 SSE 전 `search/preflight`가 문서명과 복구 행동을 돌려줘 HTTP 409이 일반 연결 오류로 축소되지 않는다.
- 상세 화면은 폭별 초기 panel 상태와 resize 정규화를 갖췄다. 1280px에서는 Context + Work, 1024px 미만에서는 Work 우선 + 상호 배타 drawer가 된다.

따라서 이 문서는 위 항목을 다시 요구하지 않는다. 남은 P0는 **실제 모델/실제 corpus로 측정·릴리스 증거를 만드는 일**이며, UI 구현 공백은 P1/P2로 분리한다.

## 현재 확인하여 유지할 것

| 흐름 | 검증한 현재 계약 | UX 판단 |
| --- | --- | --- |
| 대형 문서 | sample 범위와 선택/예상 chunk 수를 setup에 알리고, `fullReindexRequired/Ready`와 preflight를 검색 전제조건으로 사용 | sample을 완성 인덱스처럼 보이지 않게 함 |
| reindex 복구 | header의 진행/실패 재시도, Context의 `전체 색인 중`, `문서 선택 조정하기` focus 이동 | 막힌 이유와 다음 행동이 보임 |
| grounded fallback | fallback reason을 내부 코드 대신 평이한 발췌 결과 문구로 노출 | 검증 실패를 일반 생성 답변으로 숨기지 않음 |
| 다문서 진입 | flat citation을 `grouped_citations`로 보강하고 문서별 Evidence 진입점을 제공 | 문서별 provenance를 잃지 않음 |
| 반응형 기본 상태 | `initialPanels()`와 resize handler가 desktop/tablet/mobile의 기본 패널을 분리 | Core Work First에 부합 |

## P0 — 실제 릴리스 전 증거

### P0-1. benchmark를 실제 corpus/provider 기반의 재현 가능한 추천 근거로 완성한다

**관찰**

- 현재 benchmark는 `BENCHMARK_CORPUS`의 3개 하드코딩 문장과 3개 질문으로 실행된다. 모델 선택 화면은 결과가 있을 때 Recall@1/@5, MRR, latency를 정직하게 표시하지만, 계획의 대표 문서 10–20개·golden Q/A·정답 근거 라벨 조건은 아직 충족하지 않는다.
- `/embedding-benchmarks/run`은 있으나 UI에는 운영자가 새 측정/실패 모델 재측정을 시작할 행동이 없다.
- fallback provider의 결과가 `FALLBACK`으로 남아도, 실제 provider 측정과 release success를 구분한 실행 증적은 없다.

**핸드오프**

1. versioned fixture에 문서 checksum, 질문, 기대 segment id, 질문 유형을 저장한다. run에는 fixture version, model/provider/version, chunking/retrieval 조건, 실행 시각을 함께 저장한다.
2. 모델 선택 화면에는 일반 사용자의 설정 변경과 분리된 운영자용 `새 측정`/`실패 모델 다시 측정` 진입점을 둔다. 실측 1위가 현재 모델을 자동 변경하지 않는 규칙은 유지한다.
3. real provider, fallback, unavailable, partial을 서로 다른 release state로 저장하고, fallback run은 추천 품질 근거나 릴리스 통과로 쓰지 않는다.

**수용 증거**

- 세 모델이 동일한 10–20개 representative corpus와 golden segment label로 실행된 artifact를 남긴다.
- artifact에서 Recall@5 분자/분모, MRR, latency, provider/version, fixture version을 다시 확인할 수 있다.
- 실제 runtime smoke는 real provider만 통과로 기록하고 fallback/partial/unavailable은 명시적으로 비통과가 된다.

### P0-2. 실제 대형 파일·generator·다문서 release gate를 한 흐름으로 고정한다

**관찰**

현재 unit/contract test는 sample policy, preflight conflict, fallback safety, 다문서 병합을 확인한다. 하지만 실제 provider와 실제 대형 PDF/DOCX에서 07–10 전체 경로를 통과한 증거는 runtime 준비에 의존해 아직 남아 있다.

**핸드오프**

release-gate suite에 아래를 포함한다.

1. 500 chunks 초과 PDF와 DOCX: sample 비교 → 확정 → full reindex → `search/preflight` eligible → grounded 검색.
2. generator 지연, provider 미준비, invalid citation: 화면 문구·fallback citation·재시도/표시 중단 정책 검증.
3. 서로 다른 retrieval 설정의 두 문서와 인용되지 않은 선택 문서: 전역 병합과 문서별 provenance 검증.
4. 1440/1280/1024/800/390px에서 Context/Work/Output의 CTA와 recovery action screenshot 보존.

**수용 증거**

- 각 run에 provider, fallback 여부, source checksum, job id, answer artifact id, viewport screenshot이 남는다.
- `NOT_READY`, fallback, preflight conflict를 happy-path 성공으로 계산하지 않는다.

## P1 — 구현이 필요한 UX/API 계약

### P1-1. benchmark의 empty·장애·부분 성공을 같은 “미실행” 문구로 합치지 않는다

**재현**

`latestEmbeddingBenchmark()`는 404(아직 실행 안 함), 503/runtime 오류, 권한/네트워크 오류를 모두 `undefined`로 바꾼다. `benchmarkFromWire()`도 result row가 없으면 같은 값으로 바꾼다. 따라서 생성 화면은 실제 장애에도 “아직 실행하지 않았어요”라고 표시한다.

**핸드오프**

- API/client를 `not-run | ready-to-run | running | partial | completed | failed`로 구분한다.
- result row에는 model별 retryability/error와 metric `null`의 이유를 포함한다. 0%는 실제 측정값과 구분한다.
- 비교 조건이 다른 run에는 `comparabilityKey`를 두고, 공개 benchmark 참고값은 내부 실측과 같은 순위에 섞지 않는다.

**수용 증거**

- 404, 503, 빈 fixture, 2/3 모델 성공, 전체 실패 fixture가 각각 다른 상태/CTA로 렌더된다.
- partial에서도 완료 row는 남고 실패한 모델만 재측정할 수 있다.

### P1-2. 여러 sample 문서의 full-reindex 진행을 문서별로 집계한다

**재현**

adapter는 `fullReindexJob` 하나를 첫 미완료 문서에서 선택한다. sample 문서 A와 B가 동시에 full reindex 중이면 header는 한 job의 단계만 설명하고, Context는 각 문서가 대기임을 보여도 어느 문서가 실패/완료했는지 한눈에 비교하기 어렵다.

**핸드오프**

- instance detail에 문서별 `full_reindex` job summary를 배열로 제공하고, header에는 `전체 색인 1/2개 완료`처럼 집계한다.
- Context row에는 `색인 중`, `다시 시도 필요`, `검색 가능`을 텍스트/아이콘으로 함께 보여 주고 해당 문서의 retry action으로 연결한다.
- 단일 문서만 막힌 경우에는 현재처럼 나머지 ready 문서를 계속 검색 가능하게 둔다.

**수용 증거**

- A=INDEXING, B=FAILED, C=SUCCEEDED fixture에서 세 문서의 검색 가능 여부와 recovery CTA가 독립적으로 나타난다.
- A/B 선택 검색은 preflight가 모든 conflict를 반환하고 UI가 첫 오류만 일반 연결 실패로 바꾸지 않는다.

### P1-3. buffered replay SSE의 실제 단계를 화면 상태로 번역한다

**재현**

서버는 즉시 `status { phase: RETRIEVING, streaming: BUFFERED_REPLAY }`를 보낸 뒤 provider request를 완료하고, 이후 검증된 토큰을 replay한다. 그러나 프런트 `generationFromWire()`는 `phase`를 status로 변환하지 않아 UI는 기본 `문서에서 근거를 확인하고 있어요`만 보인다. `ANSWER_READY`와 “실제 생성 중 token stream이 아님”도 사용자에게 드러나지 않는다.

**영향**

느린 provider에서 사용자는 검색 중인지 생성 중인지, 또는 완성된 안전한 답을 순서대로 표시하는 중인지 알 수 없다. 이는 가짜 progress는 피하지만 현재 작업 상태도 충분히 설명하지 못하는 상태다.

**핸드오프**

- SSE 상태를 typed contract로 매핑한다: `RETRIEVING` → `문서에서 근거를 찾고 있어요`, `ANSWER_READY/BUFFERED_REPLAY` → `근거를 검증한 답변을 표시하고 있어요`, terminal generation metadata → grounded/fallback 결과.
- provider가 token streaming을 지원할 때만 그 상태를 `생성 중`으로 표시한다. 현재 `표시 중단` 라벨과 “서버 작업은 계속될 수 있음” 문구는 유지한다.
- stream disconnect 뒤 서버 결과를 answer artifact에서 열 수 있게 연결한다. 중복 질문을 유도하지 않는다.

**수용 증거**

- 지연된 provider fixture에서 `RETRIEVING → ANSWER_READY → done`이 순서대로 role=status에 한 번씩 전달되고, 토큰마다 screen reader가 반복 낭독하지 않는다.
- 표시 중단 후 artifact 상태와 화면 문구가 동일한 정책을 말한다.

### P1-4. 다문서 coverage에는 인용되지 않은 선택 문서도 포함한다

**재현**

backend 응답/SSE/artifact는 `grouped_citations`만 반환하고 `document_coverage`는 반환하지 않는다. 프런트는 flat citation을 다시 묶어 `N개 문서의 근거`를 표시한다. 따라서 선택했지만 인용 0개인 문서는 사용자에게 보이지 않는다. 현재 프런트 test도 mock으로만 `documentCoverage`를 주입한다.

**핸드오프**

1. REST, SSE done, ANSWER artifact에 선택한 모든 문서의 `documentId`, `citationCount`, `retrievedCount`, `contributed`를 반환한다.
2. 답변에는 `선택 3개 · 근거 사용 2개 · 이번 답변에 사용되지 않음 1개`처럼 표시하고, 사용되지 않은 문서에는 질문/범위 조정 행동을 연결한다.
3. UI grouping/React key는 filename이 아닌 document id를 사용한다. 같은 이름의 업로드도 안전하게 구분한다.

**수용 증거**

- 같은 파일명을 가진 두 문서와 citation 0개 문서를 함께 선택한 E2E에서 Evidence 대상과 coverage가 정확히 구분된다.
- REST/SSE/artifact의 coverage와 grouped citations가 동일하다.

### P1-5. Evidence를 citation별 원문 검증기로 완성한다

**재현**

Evidence 목록은 여러 citation을 고를 수 있지만 `openEvidence()`는 처음 연 citation의 `navigateUrl`만 lazy-load한다. 목록에서 다른 citation을 고르면 excerpt/page만 바뀌고 해당 원문을 다시 불러오지 않는다. `원문 위치 열기`도 없다.

**핸드오프**

- 선택 citation을 단일 상태로 두고 선택마다 해당 `navigateUrl`을 lazy-load한다.
- PDF page, DOCX heading, CSV/XLSX row 등 type-specific location과 `원문 위치 열기`, 이전/다음 citation을 제공한다.
- Output 안에서 닫기와 citation trigger focus 복귀를 유지하고, 800px 이하 drawer에서 실제 modal이면 backdrop/inert를 적용하거나 non-modal panel semantics로 통일한다.

**수용 증거**

- 두 문서·문서당 두 citation fixture에서 순서대로 선택한 위치의 viewer request가 발생한다.
- keyboard-only로 citation → preview → 이전/다음 → 원문 위치 → 닫기 → trigger focus 복귀를 완료한다.

## P2 — 밀도와 접근성의 제품화

| 공백 | 핸드오프 | 수용 기준 |
| --- | --- | --- |
| 1024–1379px drawer semantics | Output은 fixed overlay지만 backdrop 없이 `aria-modal`이다. 실제 modal이면 backdrop/inert, 보조 pane이면 `aria-modal` 제거 중 하나를 선택한다. | Work를 screen reader/keyboard로 동시에 조작할 수 있는지와 drawer focus trap 정책이 일치한다. |
| benchmark 정보 위계 | 결과 카드가 metric을 세 줄로 반복해 좁은 화면에서 비교가 어렵다. Recall@5를 primary로, 나머지는 disclosure/table detail로 낮춘다. | 390px에서 모델·Recall@5·상태·측정 조건이 가로 scroll 없이 보인다. |
| citation/help target | setup의 compact citation/help target은 22px 또는 title 의존이다. | citation/action은 최소 24px, 설명은 focusable popover 또는 화면 텍스트로 제공한다. |

## 우선순위 순서

1. **P0-1/2**: 실제 corpus, provider, 대형 문서, 다문서 release evidence를 먼저 확정한다.
2. **P1-1**: benchmark 상태 contract와 운영자 실행 진입점을 만든다.
3. **P1-2/3**: 대형 문서와 buffered SSE의 현재 상태를 정확히 설명한다.
4. **P1-4/5**: 모든 선택 문서의 기여와 citation별 원문 검증을 완성한다.
5. **P2**: responsive/modal semantics와 정보 밀도 회귀를 visual/a11y suite에 고정한다.

## Definition of Done

- [ ] fallback 결과는 실제 모델 quality/release success로 기록되지 않는다.
- [ ] sample/full reindex의 각 문서 상태와 검색 가능 여부가 화면·preflight·job 상태에서 일치한다.
- [ ] buffered replay와 실제 token generation은 서로 다른 진행 문구와 중단 정책을 갖는다.
- [ ] 다문서 답변은 선택한 모든 문서의 기여/무기여와 원문 근거를 구분한다.
- [ ] 어떤 지원 폭에서도 Context, Work, Output의 drawer 및 keyboard semantics가 한 가지 모델로 동작한다.
