# NotebookLM UI 2차 재리뷰 — RAG Portal

> 검토일: 2026-07-31 · 범위: `apps/frontend` · 코드 변경 없음
>
> 근거 스킬: `notebooklm-inspired-ui-skill`의 `design-principles`, `interaction-patterns`, `state-matrix`, `review-checklist`.
>
> 이 문서는 [v2 개선 명세](./NOTEBOOKLM_INSPIRED_UI_V2.md)의 구현 후속 재리뷰다. 여기의 P0/P1/P2와 수용 기준은 프론트엔드가 다음 작업 단위에 바로 적용할 지시다.

## 결론

상세 검색은 1차 리뷰보다 크게 개선됐다. `RagDetailWorkspace.tsx`는 Context–Work–Output 구조, 문서 선택과 관리의 분리, SSE 중단, 실제 citation의 원문 조회, job polling, 토큰 기반 색상을 갖췄다. 관련 테스트도 현재 7개가 통과한다.

다만 사용자에게 보이는 완성도는 아직 **상세 검색과 setup 비교 화면 사이에서 크게 갈린다.** `/rag/:id/setup`의 비교 화면은 독립 스크롤·반응형 drawer·상태 행렬·대화상자 lifecycle을 공유하지 않는다. 그리고 상세 검색도 태블릿 이하에서 패널을 진짜 drawer로 전환하지 않고 DOM 재배치/숨김하는 방식이라, Core Work First와 keyboard-only 기준을 끝까지 만족하지 못한다.

`npm test`는 2026-07-31에 통과했다(3 files, 7 tests). React Router v7 future-flag 경고는 남아 있다. 현재 테스트는 layout 실측, focus trap 복원, setup 비교, 실패 재시도, visual/a11y regression을 검증하지 않는다.

## 이미 충족한 점

| 항목 | 근거 | 판단 |
|---|---|---|
| Context와 문서 관리의 행동 분리 | `RagDetailWorkspace.tsx:714–738`의 checkbox, label, `⋯` button | `List item의 Select와 Open을 구분` 원칙에 부합. |
| Work 우선의 채팅 구조 | `RagDetailWorkspace.tsx:750–850`의 별도 messages scroll + composer | 메시지와 composer가 같은 Work panel 안에 있고, 검색 전제 조건도 인접해 표시된다. |
| 답변 중단과 부분 결과 보존 | `RagDetailWorkspace.tsx:562–592`, `785–800` | AbortController, `interrupted/failed` 시각 상태가 있다. |
| 근거와 실제 source 연결 | `RagDetailWorkspace.tsx:593–635` | citation에 `navigateUrl`이 있으면 원문을 재조회한다. |
| 처리 상태와 cancel/retry | `RagWorkspace.tsx:540–608` | job stage, 실제 completed/total, 중단, 재시도 상태가 있다. 가짜 %를 만들지 않는다. |
| 토큰 전환의 출발점 | `shared/styles/theme.ts:3–31`, `shared/ui/primitives.tsx` | shared primitive가 CSS variable 역할 토큰을 사용한다. |

## P0 — 다음 배포 전 수정

### P0-1. 태블릿·모바일을 “숨김/재배치”가 아니라 Work 중심 drawer 모델로 바꾼다

**근거**

- `RagDetailWorkspace.tsx:107–117`은 1380px 이하에서 Output을 grid의 다음 행으로 내린다.
- `RagDetailWorkspace.tsx:119–135`는 720px 이하에서 Context/Output을 `display: none`/동일 column으로 전환한다.
- header toggle은 `aria-pressed`만 사용한다(`670–698`). panel id와 `aria-controls`가 없고, mobile에서 modal drawer의 focus trap도 없다.
- `AppShell.tsx:100–109`은 workspace가 1380px 이하가 되면 outer `Main`도 스크롤하게 한다.

**지시**

1. 1440px 이상만 Context + Work + Output의 3열을 유지한다. Global nav까지 포함한 실제 최소 폭을 기준으로 검증한다.
2. 1024–1439px에서는 Context를 compact 240–272px로 유지하고 Output은 off-canvas right drawer로 전환한다. Output이 Work 아래의 20rem 섹션으로 내려가서는 안 된다.
3. 768–1023px에서는 Context와 Output 모두 drawer다. Work만 기본 노출하고 한 번에 하나의 drawer만 열 수 있게 한다.
4. 767px 이하는 질문/답변/composer만 기본 노출한다. `문서 N개`, `근거`는 full-height drawer 또는 별도 route로 연다. CSS `display:none`은 닫힌 drawer의 `inert` 상태에만 쓰고, 열린 drawer에는 `role=dialog`, `aria-modal=true`, focus trap/restore를 적용한다.
5. toggle button에는 `aria-expanded`, `aria-controls`, 명시적인 tooltip을 추가한다. rail 상태를 제공할 경우 rail에서도 같은 toggle로 복원 가능해야 한다.
6. Viewport resize 뒤 panel mode를 재계산한다. 최초 `window.innerWidth`만 읽는 방식(`469–473`)은 사용하지 않는다.

**수용 기준**

- 1440×1024: Work의 실제 사용 폭이 520px 이상이고 Context와 Evidence를 동시에 확인할 수 있다.
- 1280×800, 1024×768: Work + 보조 하나만 보이며 Output은 Work를 밀어내지 않는 drawer다.
- 390×844: 검색 질문→문서 범위 변경→citation 열기→닫기까지 가로 스크롤 없이 가능하다.
- drawer를 Escape/닫기로 닫으면 처음 연 toggle 또는 citation으로 focus가 복원된다. Tab은 열린 drawer 밖으로 나가지 않는다.

### P0-2. 원문 근거 조회 실패가 전체 workspace를 종료시키지 않게 한다

**근거**

- `RagDetailWorkspace.tsx:622–635`에서 evidence fetch 실패가 `setError`를 호출한다.
- `531`의 전역 `if (error) return <ErrorState …>` 때문에 사용자의 draft, 기존 답변, 선택 문서, Output 상태까지 모두 사라진다.

**지시**

1. `workspaceLoadError`, `evidenceLoadError`, `answerStreamError`, `documentMutationError`를 분리한다.
2. 원문 조회 실패는 Output panel 안에 `AsyncStatePanel`의 error 상태로 렌더한다. citation title/page와 `근거 다시 불러오기`를 보이고, Work와 기존 answer를 유지한다.
3. stale excerpt가 이미 있다면 지우지 않고 `원문 전체를 불러오지 못해 인용 미리보기를 보여드려요.`를 함께 표시한다.
4. detail 초기 로드 오류만 전면 ErrorState + retry가 된다.

**수용 기준**

- citation 원문 API를 실패시켜도 질문 draft, 직전 답변, 문서 선택, 열려 있던 Output panel이 유지된다.
- Output에서 retry 성공 시 같은 source heading으로 이동하고, 실패해도 global error page로 전환되지 않는다.

### P0-3. setup 비교 화면을 shared Workspace/상태 모델로 올린다

**근거**

- `RagWorkspace.tsx:20–353`의 setup 스타일은 raw px/hex/rgba와 fixed `Evidence`를 사용한다. setup에는 breakpoint가 없다.
- `648–690`의 compare input, candidate grid, sticky action bar는 작은 폭에서 wrap/drawer 정책이 없다.
- `691–727`의 Evidence/Confirm은 dialog label만 있고 focus trap, Escape, trigger focus restore, submitting/error state가 없다.
- `Candidate`(`380–431`)는 ready/no-evidence만 표현한다. preparing, streaming, failed, retry 상태가 없다.

**지시**

1. `/rag/:id/setup`을 `RagDetailWorkspace`와 동일한 workspace shell 또는 공유 `WorkspacePanel`, `EvidenceDrawer`, `ConfirmDialog`, `AsyncStatePanel`로 구성한다. setup은 Context=업로드 문서/고정 설정, Work=질문·후보 비교, Output=근거·선택 요약이다.
2. 후보 API/UI 모델에 `PREPARING | STREAMING | READY | NO_EVIDENCE | FAILED`를 추가한다. candidate별 실제 상태가 있어야 하며, 준비된 후보부터 보이고 실패 후보는 성공 후보를 막지 않는다.
3. 비교 요청과 확정 요청에 `submitting` state를 둔다. 중복 클릭을 막고, 실패 시 입력·현재 선택·결과 카드를 보존한 inline retry를 제공한다.
4. confirm은 확정 대상, 마지막 질문/답변, 삭제되는 임시 후보 수를 보여 준다. `확정하기`는 submitting 동안 busy/disabled다.
5. 비교가 한 화면에 6–9개일 때 desktop 3–4열, tablet 2열, mobile candidate switcher + 한 카드의 single-work 모드를 적용한다. 후보 카드마다 답변 영역 geometry를 동일하게 유지한다.

**수용 기준**

- 한 후보가 failed, 두 후보가 preparing, 한 후보가 ready여도 ready 후보를 선택/근거 확인할 수 있다.
- 390px에서 후보 전환, 선택, 원문 열기, 다음 라운드, 확정 확인을 가로 overflow 없이 수행한다.
- confirm/citation dialog에서 Escape, Tab/Shift+Tab, 닫기 후 focus restore가 동작한다.
- compare/finalize API 실패 후 기존 질문·선택 횟수·candidate answer가 남고 버튼으로 retry할 수 있다.

### P0-4. 검색 error에는 명시적인 “같은 조건으로 다시 시도”가 필요하다

**근거**

- streaming error 문구는 `RagDetailWorkspace.tsx:785–800`에 있으나, `queryError`(`846–850`)에는 retry control이 없다.
- `ask(question = draft)`은 재사용 가능하지만 실패한 질문/문서 범위/민감도를 user action으로 복원하는 UI가 없다.

**지시**

1. `AnswerErrorActions`에 `같은 조건으로 다시 시도`와 `질문 수정하기`를 둔다.
2. retry는 failed turn의 question, `selectedIds`, sensitivity snapshot을 사용한다. 현재 draft가 바뀌어도 failed request를 바꾸지 않는다.
3. streaming 중 `중단`은 abort만 수행한다. 완료 answer에는 Stop을 렌더하지 않는다.
4. stream 끊김, user stop, evidence 부족은 각각 다른 상태다. error tone/CTA를 공유하지 않는다.

**수용 기준**

- 네트워크 실패 뒤 retry는 같은 문서 범위·민감도·질문으로 한 번만 재요청한다.
- user stop 뒤에는 retry 대신 `이 질문 다시 보내기`가 보이며, partial text는 보존된다.
- no-evidence는 오류 CTA가 아니라 검색 범위/질문 변경 안내와 citation 없음으로 나타난다.

## P1 — 다음 기능 스프린트에 적용

### P1-1. 독립 스크롤 계약을 breakpoint별로 끝까지 지킨다

**관찰**

- Desktop에서 `ContextBody`, `.messages`, `OutputBody`의 `overflow-y:auto`는 좋은 방향이다(`150–330`).
- 그러나 1380px 이하에서 `DetailPage`가 block, workspace가 tall grid, `AppShell Main`도 scroll이 되어 outer + panel scroll이 공존한다(`30–38`, `107–117`, `AppShell.tsx:93–109`).

**지시 및 수용 기준**

- desktop: viewport는 shell만, panel body는 각 패널 하나만 scroll한다. Work composer와 setup action bar는 자기 scroll container 기준 sticky다.
- tablet/mobile: drawer 내부 body만 scroll하고 Work는 page scroll 또는 message scroll 중 하나만 선택한다. 같은 영역에 이중 scroll을 만들지 않는다.
- 200% zoom, 긴 파일명 30개, 긴 답변 10개에서 composer/action bar가 마지막 메시지·button을 가리지 않는다.

### P1-2. 도움말·탭·선택 컨트롤을 keyboard-complete로 만든다

**근거**

- setup의 `?`는 `title`만 사용한다(`RagWorkspace.tsx:402–408`). citation preview도 title뿐이다.
- Output tab은 `role=tab`이지만 `aria-controls`, `tabpanel`, Arrow/Home/End 동작이 없다(`876–900`).
- `RagCreatePage.tsx`의 `Choice` radio는 input을 `opacity:0; position:absolute`로 숨기고 `:focus-within` 표시가 없다.

**지시 및 수용 기준**

- tooltip/popover는 hover와 focus 모두에서 열리고 Escape로 닫힌다. 핵심 설명은 tooltip에만 숨기지 않는다.
- tab을 유지한다면 WAI-ARIA tabs keyboard pattern과 tabpanel 연결을 구현한다. 그렇지 않으면 tabs를 일반 button group으로 내려 `aria-pressed`로 통일한다.
- radio card는 native radio가 focus될 때 card에 focus ring을 보인다. 모든 option은 이름·설명·tradeoff를 accessible name/description으로 연결한다.
- keyboard-only로 questionnaire, detail Output view, setup candidate help를 모두 이용할 수 있다.

### P1-3. setup 처리·비교의 상태 정보 밀도를 정돈한다

**근거**

- 준비 progress 전체가 `role=status aria-live=polite`다(`RagWorkspace.tsx:553–574`). stage row가 polling마다 반복 낭독될 수 있다.
- compare header는 고정 `라운드 1`이다(`638–642`). candidate 상태·완료/진행 카운트·마지막 갱신이 없다.
- `nextRound`는 busy guard가 없어 Enter/double click으로 병렬 요청 가능하다(`517–527`, `648–656`). IME composition guard도 없다.

**지시 및 수용 기준**

- live region에는 `후보 2/3 준비 완료` 같은 변경 요약만 보낸다. stage 목록·progress bar를 live region 전체로 만들지 않는다.
- 현재 round, ready/total candidate 수, 마지막 갱신 시각을 header에 표시한다. latency 0은 `측정 중`으로 표현한다.
- compare submit은 request 중 loading state와 duplicate guard를 가지며, `Enter && !nativeEvent.isComposing`만 전송한다.
- 2초 polling 중에도 선택된 candidate와 question draft가 초기화되지 않는다.

### P1-4. 토큰 일관성을 setup/create/dashboard까지 확대한다

**근거**

- shared theme은 역할 토큰으로 전환됐지만(`theme.ts:3–31`), `RagWorkspace.tsx:20–353`, `RagCreatePage.tsx`, `RagDashboardPage.tsx`에는 raw `px`, `rgba`, `#b7cdf9`, `#e1f0e9`, inline style이 남아 있다.

**지시 및 수용 기준**

- layout, spacing, radius, shadow, z-index, interactive surface까지 `assets/design/rag-portal-tokens.css`의 semantic token을 확장·사용한다.
- primary/secondary/danger/button, candidate selected, citation, progress, dialog surface에 새 hex를 추가하지 않는다.
- setup과 detail의 PanelHeader 높이, card radius, focus ring, citation chip, dialog shadow가 동일한 token 값을 사용한다.
- `grep` 기반 점검에서 화면 컴포넌트의 새 색상 hex/새 magic spacing이 0개다(기존 제거는 별도 cleanup PR 가능).

### P1-5. 처리 취소·재시도의 실패 경로를 명시한다

**근거**

- `cancelPreparation`/`retryPreparation`은 network failure를 catch하지 않는다(`485–493`).
- detail의 `busy`는 answer stream, 문서 upload, 문서 delete에 공유된다(`480`, `562–592`, `637–665`). 문서 mutation 중에도 Work header가 `답을 찾고 있어요`가 될 수 있다.

**지시 및 수용 기준**

- `answerState`, `jobMutationState`, `documentMutationState`를 구분한다. Stop 버튼은 answer stream이 active일 때만 보인다.
- cancel/retry/upload/delete 실패는 해당 panel/dialog 내부에 inline error + retry를 보이고 global workspace를 유지한다.
- 문서 업로드 중에도 기존 search answer와 composer 상태는 의미에 맞게 유지/비활성화된다.

## P2 — 구조적 완성도와 운영성

### P2-1. Answer를 관리 가능한 Output 객체로 만든다

현재 detail은 마지막 answer 한 개만 유지한다(`464–466`, `766–800`). `AnswerArtifact`/turn list에 title, context snapshot, status, timestamp, citations, retry/copy/open action을 두고 Output에 `최근 답변` view를 추가한다. 새 질문이 이전 답변을 덮지 않아야 한다.

**수용 기준:** 두 질문을 수행한 뒤 이전 answer의 citation을 다시 열고, 각 answer가 생성 당시의 문서 범위를 표시한다.

### P2-2. panel preference와 deep link를 URL/UI preference로 복구한다

panel open/view는 local state뿐이다(`469–475`). Workspace 재방문 시 Context/Output mode와 열린 evidence가 사라진다.

**수용 기준:** `?panel=output&evidence=<id>`로 근거를 열 수 있고, user preference(rail/default)는 세션 동안 유지된다. server job state는 UI store에 복제하지 않는다.

### P2-3. dead legacy UI와 visual/a11y regression을 정리한다

`RagWorkspace.tsx:733–963`의 `LegacyRagDetailPage` 및 그 전용 styles는 route에 사용되지 않는다(`964`에서 새 detail export). setup extraction 뒤 삭제하거나 tests와 shared components로 대체해 디자인 drift를 막는다.

**수용 기준:** 1440/1280/1024/768/390 viewport visual regression, axe, 200% zoom, reduced motion, focus-trap restore, setup failed candidate/confirm error를 CI에서 검증한다.

## 화면별 Definition of Done

### 상세 검색 (`RagDetailWorkspace.tsx`)

- Context 문서 범위와 Work 질문/답변, Output 근거/설정/문서 관리의 역할이 구분된다.
- citation→source→원문 excerpt 실패가 Work를 중단시키지 않는다.
- streaming, interrupted, failed, no-evidence, ready는 서로 다른 문구·CTA·색/아이콘/텍스트를 갖는다.
- desktop의 세 panel, tablet/mobile의 drawer가 같은 focus/scroll 계약을 따른다.

### setup 비교 (`RagWorkspace.tsx`)

- upload, processing, candidate preparation, streaming comparison, failed candidate, multi-select, tie, finalization의 상태 행렬이 있다.
- 답변과 근거, 선택 횟수, candidate 상태, 처리 지연 이유를 카드별/화면별로 혼동 없이 읽을 수 있다.
- 최종 확정은 focus-safe confirm과 request error/retry를 거쳐야 하고, 임시 결과가 정리된다는 영향을 명시한다.
- mobile은 후보 하나씩 비교하는 single-work mode다.

### 공통 (`AppShell`, `theme`, `primitives`)

- Global nav는 Context와 구분되고, 좁은 화면에서 workspace의 Work 폭을 잠식하지 않는다.
- panel toggle, icon action, help/citation은 tooltip·accessible name·focus-visible을 제공한다.
- shared semantic tokens만 사용하며 같은 역할의 UI가 route마다 다른 색/spacing/dialog behavior를 갖지 않는다.

## 리뷰 체크 결과

| 스킬 체크 항목 | 현 상태 | 다음 행동 |
|---|---|---|
| Context / Work / Output 역할 | 상세은 대체로 충족, setup 미충족 | P0-1, P0-3 |
| 중앙 Work 우선과 안정 geometry | desktop 일부 충족 | P0-1, P1-1 |
| 필요 없는 패널 제거 | dashboard/create는 적절 | setup에 conditional Output 적용 |
| 상태 행렬 | detail 일부, setup 부족 | P0-3, P1-3, P1-5 |
| 준비/생성/중단/retry | detail stream과 job 일부 충족 | P0-4, P1-5 |
| verification first-class | citation 연결은 충족 | P0-2, P1-2 |
| mobile 단일 작업 | intent만 있고 drawer 미구현 | P0-1 |
| keyboard/focus lifecycle | detail citation Escape 일부 충족 | P0-1, P0-3, P1-2 |
| token-only styling | shared 일부 충족 | P1-4 |
| visual/a11y regression | 미충족 | P2-3 |
