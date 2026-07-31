# Sprint 06 — 후보 준비 상태 UX 검토

> 범위: setup 비교 화면의 후보 카드 · 상태: `PREPARING`, `READY`, `FAILED`, `NO_EVIDENCE`
>
> 원칙: Core Work First, Visible System Status, Reversible Exploration, No Invisible Prerequisites. 상태는 색상만이 아니라 아이콘·문구·행동으로 함께 전달한다.

## 결정 요약

- 후보는 **카드 위치를 고정**한다. 준비 완료 순서로 카드가 이동하거나, 로딩 중인 카드를 제거하지 않는다.
- 사용자는 `READY` 후보만 이번 라운드에 선택할 수 있다. `NO_EVIDENCE`는 신뢰할 만한 fallback 결과로 **비교 대상에는 남기되 투표 대상은 아니다**. 근거 없는 결과가 최종 방식으로 확정되는 것을 막기 위함이다.
- 하나라도 READY가 있으면 준비된 후보부터 바로 비교할 수 있다. 모든 후보가 준비될 때까지 화면을 막지 않는다.
- 실패·근거 부족은 전역 오류가 아니라 후보 카드 안의 상태다. 다른 후보의 비교·선택·다음 라운드를 막지 않는다.
- 단독 1위 확정은 **이번 라운드에서 선택된 READY 후보만** 누적 선택 횟수에 더한다. 동점/선택 없음/READY 없음은 완료를 비활성화하고 이유를 보인다.

## 1. 상태 계층과 카드 공통 구조

각 `PipelineCandidateCard`는 순서와 높이의 기준을 유지한다.

```text
카드 header: [checkbox 또는 상태 아이콘] 후보 이름 · 검색 방식 도움말 · 선택 N회
상태 row: 상태 배지 + 한 줄 설명
본문: 답변 또는 상태별 placeholder (최소 답변 영역 높이 유지)
하단: 후보별 행동                         응답 시간/상태 메타데이터
```

1. **후보 이름/선택 횟수**가 첫 번째다. 이름은 `조항 단위 · 일반 검색`처럼 쉬운 명칭을 사용한다.
2. **상태**가 두 번째다. 색상만으로 구분하지 않는다.
3. **답변/근거**가 세 번째다. READY의 답변은 문장 안 citation chip과 함께 표시한다.
4. **행동**은 카드 하단에 둔다. 한 카드에는 primary 행동을 하나만 둔다.
5. 기술 원리·오류 원문은 도움말/popover 또는 `세부 정보` 안에 둔다. 기본 비교 화면을 로그 화면처럼 만들지 않는다.

`aria-label`에 후보명, 준비 상태, 선택 가능 여부, 누적 선택 횟수를 포함한다. 예: `조항 단위 일반 검색, 준비 완료, 현재 2회 선택, 이번 라운드에서 선택`.

## 2. 상태별 한국어 문구·행동

| 상태 | 카드 배지/아이콘 | 본문 문구 | 선택 | 카드 행동 | 시각 hierarchy |
|---|---|---|---|---|---|
| `PREPARING` | `◐ 준비 중` (progress) | `이 방식을 비교할 답변과 근거를 준비하고 있어요.` | 불가 | 없음. 장기 지연이면 `준비 상태 보기` text action | neutral surface + 2–3줄 skeleton. 후보 이름과 카드 위치는 고정. |
| `READY` | `✓ 비교 가능` (success) | 답변 본문 + 인라인 citation | 가능 | `원본 조각만 보기` text action | 기본 surface. 선택되면 soft brand border/surface와 checkbox check를 함께 표시. |
| `FAILED` | `! 준비 실패` (danger) | `이 방식은 준비를 마치지 못했어요. 다른 후보는 계속 비교할 수 있어요.` | 불가 | `다시 준비하기` secondary. 원인 있으면 `세부 정보` | danger soft surface는 상태 줄에만 제한. 답변 영역은 최소 높이를 유지. |
| `NO_EVIDENCE` | `! 근거를 찾지 못함` (warning) | `이 질문을 뒷받침할 문서 근거를 찾지 못했어요.` | 불가 | `질문 바꾸기` text action. citation 미표시 | warning soft surface. 오류처럼 빨간색으로 과장하지 않는다. |

### 상태별 보조 문구

- PREPARING, 아직 일부 후보만 준비됨: `준비된 후보부터 비교할 수 있어요. 2개 중 1개 준비 완료`
- PREPARING, 모델 지연/재시도: `모델을 준비하고 있어요. 평소보다 조금 더 걸릴 수 있어요.`
- FAILED, 재시도 불가: `준비를 다시 시작할 수 없어요. 다른 후보를 비교하거나 문서를 다시 준비해 주세요.`
- FAILED, 재시도 중: `다시 준비하고 있어요. 이 카드는 같은 위치에서 갱신됩니다.`
- NO_EVIDENCE, 모든 후보 해당: `이 질문에는 비교할 수 있는 근거가 없어요. 문서 범위나 질문을 바꿔 주세요.`
- READY, 첫 준비 완료: `이 후보는 비교할 준비가 됐어요.` (live region에 한 번만 요약)

피할 표현: `정확도 0점`, `검색 실패`, `LLM 오류`, `결과 없음`만 단독 표기. 비전문가에게 원인과 다음 행동이 없는 기술 실패 코드도 직접 노출하지 않는다.

## 3. 선택·라운드·확정 동작

### 선택 규칙

1. READY 후보의 checkbox만 enabled다. checkbox가 아닌 카드 전체 click으로 선택을 토글하지 않는다.
2. PREPARING/FAILED/NO_EVIDENCE checkbox는 렌더하지 않거나 disabled 상태와 이유를 함께 노출한다. disabled checkbox만 두고 이유를 숨기지 않는다.
3. 선택은 복수 가능하다. 선택한 후보들의 **이번 라운드 임시 선택**과 **누적 선택 횟수**를 구분해 표시한다.
4. 후보가 `READY → FAILED`로 전환되면 이번 라운드 선택은 해제하고 `준비 상태가 바뀌어 선택을 해제했어요.`를 status region으로 알린다. 다른 후보를 자동 선택하지 않는다.
5. 후보가 PREPARING에서 READY가 되어도 사용자의 현재 scroll position·선택·질문 draft를 변경하지 않는다.

### 하단 action bar

```text
준비됨 3/6 · 이번 라운드 1개 선택
[다음 라운드 진행]  [완료(조항 단위 · 일반 검색)]
```

- `다음 라운드 진행`: READY 선택이 있으면 투표 후 다음 질문을 비교한다. 선택이 없으면 `이번 질문에서는 고르지 않음`으로 처리하고 다음 라운드로 갈 수 있다.
- `완료`: 단독 1위 READY 후보가 있을 때만 enabled다. disabled 이유는 버튼 옆에 항상 텍스트로 둔다.

| 완료 불가 이유 | 화면 문구 |
|---|---|
| READY 후보 없음 | `아직 비교할 준비가 된 후보가 없어요.` |
| 이번까지 선택 없음 | `답변과 근거를 보고 도움이 된 후보를 하나 이상 골라 주세요.` |
| 최다 득표 동점 | `아직 한 가지 방식이 앞서지 않았어요. 다음 질문에서도 비교해 주세요.` |
| 확정 요청 중 | `확정 정보를 저장하고 있어요.` |

### 확인 대화상자

완료를 누르면 즉시 확정하지 않는다.

```text
이 방식으로 확정할까요?
조항 단위 · 일반 검색 · 누적 선택 3회

마지막으로 비교한 질문과 답변
다른 임시 후보 5개는 정리됩니다.

[다시 비교하기] [확정하기]
```

- 기본 focus는 `다시 비교하기`다.
- confirm에는 후보의 마지막 READY 답변과 citation 수를 보여 준다. NO_EVIDENCE/FAILED 후보는 우승 후보가 될 수 없으므로 확정 요약에 포함하지 않는다.
- `확정하기` 이후에는 submitting 상태가 되고 중복 요청을 막는다. 실패하면 dialog 안에서 오류와 `다시 시도`를 보여 주며 dialog·비교 결과를 유지한다.
- Escape, 닫기, `다시 비교하기`는 비교 화면의 완료 버튼으로 focus를 복원한다. Tab/Shift+Tab은 dialog 내부에서 순환한다.

## 4. Mobile 후보 전환기

모바일은 6–9개 카드를 세로로 길게 나열하는 화면이 아니다. 한 번에 **후보 하나를 깊게 확인하고 선택하는 single-work mode**다.

```text
라운드 2 · 준비됨 3/6
보고 있는 후보 [조항 단위 · 일반 검색 ▾]

[후보 카드 1개]

선택 1개 · 단독 1위 없음
[다음 라운드] [완료]
```

1. `보고 있는 후보`는 native select 또는 접근 가능한 listbox/button + bottom sheet로 구현한다. option에는 `준비 중`, `비교 가능`, `근거 없음`, `준비 실패` 상태를 텍스트로 함께 읽힌다.
2. 후보를 바꿔도 선택 상태와 카드별 읽기 위치는 유지한다. 전환 과정에서 답변 내용을 자동 scroll-to-top 하지 않는다.
3. 준비 중/실패/근거 없음 후보도 switcher에는 남긴다. “비교에서 사라진” 것처럼 보이면 안 된다.
4. citation은 full-height Evidence drawer/route로 열고 닫을 때 citation으로 focus를 돌린다.
5. action bar는 safe-area를 고려한 sticky footer에 둔다. primary/secondary 모두 44px 이상의 touch target을 갖는다.
6. 후보를 비교하기 위해 hover에 의존하지 않는다. 도움말·상태·선택 횟수는 카드에 항상 표시한다.

## 5. 상태 전이와 live region

```text
PREPARING ──성공──> READY ──질문에 근거 없음──> NO_EVIDENCE
    │                   │
    └──실패──> FAILED ──다시 준비──> PREPARING
```

- `NO_EVIDENCE`는 해당 **질문·라운드의 answer 상태**다. 파이프라인 자체가 영구 실패했다는 의미가 아니다. 다음 라운드에서 READY로 바뀔 수 있다.
- `FAILED`는 후보 준비/index 상태다. 재시도 성공 뒤 새 라운드 answer를 받아야 READY 또는 NO_EVIDENCE가 된다.
- PREPARING의 skeleton은 `aria-busy=true`를 쓴다. 토큰마다 live announce하지 않는다.
- live region에는 전환 요약만 보낸다. 예: `후보 3개 중 2개를 비교할 수 있어요.`, `표 중심 검색 준비에 실패했어요. 다시 준비할 수 있어요.`
- 상태 변경은 `role=status`, 요청 오류는 `role=alert`로 구분한다.

## 6. API/UI 최소 계약

프론트 mock과 API는 candidate별 상태를 같은 문자열로 제공한다. 프론트가 answer/evidence 유무를 추론해 FAILED와 NO_EVIDENCE를 혼동하지 않는다.

```ts
type CandidateReadiness = 'PREPARING' | 'READY' | 'FAILED';
type CandidateAnswerState = 'PENDING' | 'READY' | 'NO_EVIDENCE' | 'FAILED';

type CandidateComparisonView = {
  id: string;
  displayName: string;
  readiness: CandidateReadiness;
  answerState: CandidateAnswerState;
  selectionCount: number;
  roundSelectionAllowed: boolean;
  statusMessage?: string;     // 사용자 노출 가능한 문장
  retryable: boolean;
  answer?: string;
  citations: Citation[];
  latencyMs?: number;
};
```

- 화면에는 readiness와 answer state를 조합해 위 네 가지 표현으로 매핑한다. `PREPARING`은 준비 중, `FAILED`는 준비 실패 또는 답변 생성 실패, `NO_EVIDENCE`는 준비가 정상 완료됐으나 근거가 없는 결과다.
- `retryable`이 false면 retry CTA를 숨기고 대체 행동을 보인다.
- `roundSelectionAllowed`는 backend가 보낸 상태가 아니라 frontend guard만으로도 강제한다: `readiness === READY && answerState === READY && citations.length > 0`.
- ready/failed/no-evidence가 섞인 partial 상태는 정상적인 비교 화면이며 전역 error가 아니다.

## 7. Sprint 06 acceptance checklist

- [ ] 후보 카드의 DOM 순서와 grid 위치가 PREPARING→READY 전환 중 바뀌지 않는다.
- [ ] READY 후보만 checkbox로 선택할 수 있고, 선택 control에는 후보명·상태·누적 선택 횟수가 읽힌다.
- [ ] PREPARING은 같은 높이의 skeleton과 `준비 중` 문구를 표시하며, 준비된 후보의 비교를 막지 않는다.
- [ ] FAILED는 원인/재시도 가능 여부/대체 행동을 card 안에서 제공하고 다른 후보를 막지 않는다.
- [ ] NO_EVIDENCE는 warning 표현·citation 없음·질문/범위 변경 행동을 제공하며, 최종 선택/확정에 포함되지 않는다.
- [ ] READY·NO_EVIDENCE·FAILED가 한 라운드에 섞인 fixture가 있다.
- [ ] 현재 라운드의 준비됨 수와 선택 수, 완료 불가 이유가 action bar에 항상 보인다.
- [ ] 동점, 선택 없음, READY 없음, 확정 요청 중에 완료 CTA의 상태와 이유가 각각 다르다.
- [ ] confirm dialog는 마지막 READY answer, citation 수, 임시 후보 정리 영향을 보여 주고 focus trap/restore 및 error retry를 지원한다.
- [ ] 1440px에서 후보 3–4열, 1024px에서 2열, 390px에서 switcher + 1카드로 동작한다.
- [ ] mobile의 후보 전환·checkbox·citation·하단 action은 keyboard와 touch로 모두 동작하며 hover에 의존하지 않는다.
- [ ] screen reader에는 후보 준비 전환 요약만 한 번 알리고, streaming/skeleton 본문을 반복 낭독하지 않는다.
