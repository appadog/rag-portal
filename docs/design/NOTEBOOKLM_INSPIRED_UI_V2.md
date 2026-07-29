# RAG Portal v2 — NotebookLM-Inspired UI 개선 명세

> v2는 [RAG Portal UX 핸드오프 v1](./RAG_PORTAL_UX_HANDOFF.md)를 대체하지 않고, 현재 `apps/frontend` 구현을 감사해 **즉시 적용할 구조·상태·접근성 기준**을 추가한다. 충돌할 경우 이 문서의 v2 정책을 우선한다.

## 1. 감사 결론

현재 구현은 비전문가 중심의 질문→업로드→비교→근거 확인 흐름과 차분한 시각 톤을 잘 시작했다. 특히 후보 카드의 다중 선택, 동점 시 확정 비활성화, 문서 범위에 따른 검색 화면 분리는 제품 계획과 일치한다.

다음은 구조적으로 보완해야 한다. 이는 미관보다 신뢰성과 작업 완료율에 영향을 준다.

| 우선 | 관찰한 현재 상태 | v2 결정 |
|---|---|---|
| P0 | `body { min-width: 768px }`이고 주요 화면에 breakpoint가 없다. | 모바일을 단순 축소하지 않고 단일 작업 흐름으로 전환한다. `min-width`를 제거한다. |
| P0 | 상세 문서 행이 `button` 안에 `checkbox`를 넣어 중첩 인터랙션이 된다. | 행의 **열기**와 checkbox의 **검색 범위 선택**을 분리한다. 한 요소가 두 행동을 암시하지 않는다. |
| P0 | 근거 패널은 fixed overlay지만 포커스 trap/복원·반응형 drawer 규칙이 없다. | `EvidenceDrawer`를 dialog로 표준화한다. citation별 실제 source/segment로 연다. |
| P0 | 모든 후보가 준비 완료처럼 렌더링되고 partial/failed/streaming 상태가 없다. | 후보·답변·작업의 상태 행렬을 도입하고 geometry를 유지한다. |
| P0 | CSS 토큰을 import했지만 theme·컴포넌트에는 hex/px/transition 값이 다수 하드코딩됐다. | 토큰을 styled-components theme에 매핑하고 역할 토큰만 사용한다. |
| P1 | 상세은 Context+Work 2열이고 Output은 근거를 눌렀을 때만 임시 overlay다. | Workspace route에는 Context / Work / Output 역할과 패널·스크롤 계약을 둔다. 모든 화면에 3패널을 강제하지는 않는다. |
| P1 | 검색 방식 버튼은 실제 선택 상태·option 범위·도움말 popover가 없다. | `SearchModeSelect` 한 컴포넌트에서 문서 범위 기반 option, 선택 상태, 키보드 접근 가능한 설명을 제공한다. |
| P1 | create의 숨은 radio는 키보드 focus를 시각적으로 드러내지 않는다. | native input과 card label을 연결하고 `:focus-within`/`aria-describedby`를 적용한다. |
| P2 | 결과 답변은 일회성 메시지이며, 생성 결과의 상태/시각/근거를 관리하는 객체 모델이 없다. | `AnswerArtifact` 또는 대화 turn을 결과 객체로 모델링하고 최근 답변/근거를 Output panel에서 다시 연다. |

### 현재 코드에 대한 구체적 주의

- `RagDetailPage`에서 인용을 열 때 `detail.candidates[0]`가 사용된다. 실제 `answer.citations`의 source/segment와 연결해야 한다.
- `Evidence`는 detail에서 `aria-modal`, focus 이동/복원, Escape 닫기, 화면폭별 배치가 없다. setup의 confirm dialog도 focus trap은 없다.
- `?` 설명은 `title`에만 의존한다. pointer hover가 아닌 keyboard focus에서도 읽을 수 있는 popover 또는 항상 보이는 설명이 필요하다.
- Dashboard에는 `items.length === 0` 전용 EmptyState가 없고, 상세 조회 실패도 별도 오류·재시도 상태가 없다.
- `StatusBadge`의 READY가 progress와 같은 파랑 계열이다. 성공/처리의 의미를 색·아이콘·문구 모두에서 분리한다.
- `Button` primary hover가 현재 브랜드 팔레트와 다른 초록색으로 바뀐다. action role token으로 교체한다.

## 2. 역할 기반 정보 구조

### 2.1 Context → Work → Output 정의

| 역할 | 사용자 질문 | RAG Portal의 책임 | 대표 요소 |
|---|---|---|---|
| Context | “무엇을 기준으로 작업 중인가?” | 선택 문서, 검색 범위, 현재 RAG, 질문 조건을 항상 확인 가능하게 한다. | 문서 목록, 범위 checkbox, 모델/모드 요약 |
| Work | “지금 내가 해야 할 일은 무엇인가?” | 가장 넓고 안정적인 영역에서 질문·비교·읽기·확정을 수행한다. | composer, 비교 카드, 답변 메시지, 설정 질문 |
| Output | “무엇이 만들어졌고 어떻게 확인/관리하나?” | 근거, 최근 답변, 처리 상태, 확정 결과를 독립 객체처럼 열고 재확인한다. | Evidence viewer, 답변 기록, job detail, 확정 요약 |

Context는 전역 사이드바와 다르다. 현재 `AppShell`의 `내 지식 공간/새로 만들기/처음이신가요?`는 **Global navigation**이고, `RagDetailPage` 안의 문서 목록이 Context다.

### 2.2 화면별 적용

| Route/화면 | Context | Work | Output | v2 레이아웃 판단 |
|---|---|---|---|---|
| `/rag` 대시보드 | collection filter/상태 요약 | 인스턴스 카드 탐색·재개 | 카드 내 상태·다음 행동 | 3패널 불필요. 목록이 Work이며 상태는 카드에 압축한다. |
| `/rag/new` 설정 | 지금까지의 답, 진행 단계 | 한 번에 한 질문 | 모델 추천 이유 | 1열. 추천 이유는 accordion/drawer; 불필요한 패널 금지. |
| `/rag/:id/setup` 업로드·처리 | RAG 이름, 고정 모델, 업로드 문서 | dropzone 또는 단계 상태 | job 단계/완료 후보 수 | 1–2열. processing의 진행 세부 정보는 접을 수 있는 output section. |
| `/rag/:id/setup` 비교 | 선택 문서·라운드·고정 조건 | 질문 composer + 후보 비교 grid | 선택 요약 + 열려 있는 근거 | 데스크톱에서는 Context + Work + conditional Output. evidence가 없을 때 Output은 rail/닫힘 상태다. |
| `/rag/:id` 실사용 검색 | 문서 범위·검색 모드 | 대화/답변/composer | Evidence viewer + 최근 답변 기록 | v2의 대표 3패널 workspace. 설정 스펙은 Work의 별도 탭(읽기 전용)으로 유지한다. |

### 2.3 Output은 객체다

현재 답변은 화면에만 존재한다. v2에서는 아래 상태를 가진 `AnswerArtifact`/대화 turn을 최소한 UI 모델로 관리한다. 서버 영속화는 backend와 협의하되, UI 구조는 먼저 같은 shape를 mock에 적용한다.

```ts
type AnswerArtifact = {
  id: string;
  title: string;                    // 질문 첫 48자 또는 사용자 지정 제목
  status: 'queued' | 'generating' | 'ready' | 'failed' | 'stopped';
  context: { ragId: string; documentIds: string[]; searchMode?: string };
  createdAt: string;
  updatedAt: string;
  citations: Citation[];
  can: Array<'open' | 'copy' | 'retry' | 'stop' | 'delete'>;
};
```

Output panel은 “Studio”라는 외부 제품의 용어를 복제하지 않는다. 사용자에게는 `근거와 답변 기록`으로 부른다. MVP에서 저장이 아직 없다면 `이번 검색의 근거`라는 임시 output으로 시작하고, `최근 답변`은 확장 과제로 표기한다.

## 3. 레이아웃·패널·스크롤 정책

### 3.1 Desktop (1440px 이상)

상세/비교 workspace는 아래의 안정된 geometry를 쓴다. 3개의 내부 패널이 아닌 Global nav까지 4개의 큰 표면을 만들지 않도록, workspace route의 Global nav는 64px rail로 축소한다.

```text
┌─ Global rail 64 ┬─ Context 288 ┬──────── Work min 520 ────────┬ Output 344 ┐
│ product/nav     │ documents     │ messages / comparison + composer │ evidence  │
└─────────────────┴───────────────┴──────────────────────────────────┴───────────┘
```

- 바깥 캔버스 padding 16px, panel gap 16px, panel header는 모두 56px이다.
- Context `240–420px`, Work 최소 `520px`, Output `280–480px`를 [토큰](../../assets/design/rag-portal-tokens.css)으로 관리한다.
- Work 본문은 `--rp-reading-width` 내에서 읽기 폭을 제한한다. 비교 grid만 Work의 전체 폭을 쓴다.
- Output이 닫히면 64px rail만 남기고, `근거 열기` icon button에 `aria-expanded`와 label을 제공한다. 근거를 연 뒤에는 Output panel이 자동 확장될 수 있다.

### 3.2 Tablet (1024–1439px)

- Global nav는 64px rail이다.
- Context는 기본 272px으로 유지한다. Output은 항상 drawer이며, evidence를 열었을 때만 화면 우측에서 나온다.
- 비교 카드는 최소 18rem으로 2열을 우선한다. Work가 520px 이하가 되려 하면 Output을 숨기고 Context를 compact mode로 전환한다.
- panel resize를 구현하는 경우 keyboard 가능한 separator여야 한다. MVP에서 resize를 제공하지 않으면 고정 폭+collapse만 제공한다.

### 3.3 Small tablet (768–1023px)

- Global nav는 56px topbar로 전환한다. Context와 Output은 모두 drawer다.
- 화면의 기본은 Work 하나다. `문서 (N)`와 `근거` 버튼이 Work header에 있고, 동시에 두 drawer를 열지 않는다.
- 비교는 2열이 가능한 폭에서만 2열이다. 그렇지 않으면 후보 선택 요약을 sticky footer에 남기고 한 장씩 전환할 수 있다.

### 3.4 Mobile (767px 이하)

모바일 목표는 데스크톱 workspace의 축소가 아니라 **질문 하나를 완결하는 것**이다. `body min-width: 768px`은 제거한다.

- 기본 화면은 Work: 질문, 답변, composer 한 열.
- Context는 `문서 2개` button으로 여는 full-height dialog/drawer다. 변경 후 `2개 문서에서 검색`이라는 visible label을 갱신한다.
- citation은 full-height Evidence route/drawer로 열며 Back/Escape/닫기로 원래 chip에 focus를 복원한다.
- 6–9개 후보 비교는 카드 1개 + 후보 전환 select/listbox + 고정 선택 요약으로 처리한다. 가로로 6개 카드를 강제하지 않는다.
- primary CTA와 composer는 safe-area inset을 고려한 sticky footer 안에 둔다. touch target은 44px 이상이다.

### 3.5 스크롤 소유권 계약

| 영역 | 스크롤 소유 | 고정 요소 |
|---|---|---|
| AppShell | viewport 하나만 | global header/topbar |
| Context panel | 문서 목록만 독립 scroll | panel header, 문서 추가 CTA |
| Work: search | 대화 메시지 목록만 scroll | header/tab, composer footer |
| Work: comparison | 페이지 또는 비교 body 하나 | 라운드/질문 header, 선택 action bar |
| Output | evidence/answer 기록 본문만 scroll | panel header/close |
| Dialog/drawer | dialog body만 scroll | header/close, 필요 시 footer action |

`position: fixed` 근거 패널을 Work 위에 임의로 띄우지 않는다. sticky는 해당 scroll container 안에서만 사용한다. 로딩/스트리밍 때 panel의 너비·높이와 composer 위치가 흔들리지 않아야 한다.

## 4. 컴포넌트 상태 행렬

아래 행렬은 shared component의 테스트·Storybook/mock fixture 기준이다. 모든 상태가 API 구현 전에 재현 가능해야 한다.

| 컴포넌트 | 상태 | 화면/행동 | 접근성 |
|---|---|---|---|
| `WorkspacePanel` | hidden / rail / compact / default / expanded | hidden은 inert, rail은 icon만, 나머지는 metadata 밀도를 바꾼다. | toggle: `aria-expanded`, `aria-controls`; drawer는 trap+restore |
| `DocumentScopeItem` | default / hover / selected / processing / failed / unavailable | 선택 checkbox와 문서 열기를 분리; processing은 실제 단계, failed는 재시도/상세. | checkbox label은 파일명+검색 포함 여부, open은 독립 button |
| `PipelineCandidateCard` | preparing / streaming / ready / no-evidence / failed / selected | preparing은 동일 card geometry skeleton; streaming은 stop 가능 여부를 표시; failed는 다른 후보를 막지 않음. | checkbox는 status·누적 선택 횟수를 포함한 name; live region은 상태 요약만 |
| `AnswerComposer` | idle empty / typing / submitting / generating / stopped / error / disabled | generating에는 Stop, error에는 retry, disabled에는 이유. IME Enter는 제출하지 않는다. | label, hint/error `aria-describedby`, status name 변경 |
| `CitationChip` | default / hover / focus / open / unavailable | hover와 focus에서 preview, click/Enter에서 source 이동; citation이 없으면 chip 미렌더. | `button`, source title·location을 accessible name에 포함 |
| `EvidenceDrawer` | closed / opening / open / loading / failed | source heading→highlighted excerpt; 실패는 source id와 retry. | `role=dialog`, `aria-modal=true`, Escape, focus trap/restore |
| `RagStatusBadge` | setting-up / parsing / indexing / tuning / ready / failed | 실제 상태+진행수+최종 갱신만 노출; 가짜 % 금지. | icon + status text, update는 요약 live region |
| `AsyncStatePanel` | initial / loading / refreshing / empty / partial / stale / offline / forbidden / failed | 기존 성공 콘텐츠는 refresh 중 유지, partial은 성공/실패 항목을 함께 표시. | status와 retry action의 명확한 이름 |
| `FinalizationDialog` | closed / review / submitting / error / succeeded | review에는 1위, 마지막 Q/A, 정리 영향. submitting 중 중복 요청 차단. | first focus=되돌아가기, trap/restore, destructive impact 텍스트 |

## 5. 토큰·컴포넌트 구현 계약

### 5.1 토큰

v2는 `assets/design/rag-portal-tokens.css`에 Workspace geometry, z-index, elevated/hover surface, dialog shadow를 추가했다. `theme.ts`는 이를 **역할 이름으로** 매핑한다. CSS variable을 직접 읽든 TypeScript theme에 같은 값을 정의하든 한 가지 source of truth를 정한다.

권장 매핑은 다음과 같다.

```ts
const theme = {
  colors: {
    canvas: 'var(--rp-canvas)',
    surface: 'var(--rp-surface)',
    surfaceHover: 'var(--rp-surface-hover)',
    surfaceSelected: 'var(--rp-surface-selected)',
    textPrimary: 'var(--rp-ink)',
    textSecondary: 'var(--rp-ink-subtle)',
    borderDefault: 'var(--rp-border)',
    actionPrimary: 'var(--rp-action)',
    actionPrimaryHover: 'var(--rp-action-hover)',
    success: 'var(--rp-status-success)',
    warning: 'var(--rp-status-warning)',
    danger: 'var(--rp-status-danger)',
  },
  layout: {
    contextDefault: 'var(--rp-context-panel-default)',
    coreMin: 'var(--rp-core-work-min)',
    outputDefault: 'var(--rp-output-panel-default)',
  },
};
```

- component 안의 `#hex`, `14px`, `.18s`, `rgba(...)`은 새로 추가하지 않는다. semantic token이 없으면 먼저 token을 만든다.
- `Card`는 기본 surface, interactive, flat 세 variant 정도로 한정한다. 모든 section을 Card로 감싸지 않는다.
- `Button`은 `primary | secondary | ghost | text | danger`를 명시하고 `loading` 상태를 갖는다. boolean style prop 대신 `variant`, `state`, `density`를 쓴다.
- 고빈도 panel resize 값만 CSS variable로 전달한다. 서버 데이터나 panel open state는 style props로 흘리지 않는다.

### 5.2 상태 분리

| 상태 종류 | 보관 위치 | 예시 |
|---|---|---|
| Server state | TanStack Query/API hook | RAG, documents, jobs, candidates, answers |
| Client UI state | local state 또는 작은 UI store | panel mode, selected document IDs, active evidence, draft question |
| URL state | route/search params | rag ID, active tab, 열려 있는 document/evidence ID, 공유할 filter |

server job progress나 answer stream 결과를 Zustand/local UI state에 중복 저장하지 않는다. job ID를 기준으로 재조회/복구한다. Evidence viewer처럼 URL로 공유할 가치가 있는 detail은 `?evidence=<segmentId>`를 고려한다.

### 5.3 React 경계

- Page: route, query loading/error, feature composition, panel ErrorBoundary.
- Feature: 비교 투표·업로드·검색 mutation, UI orchestration.
- Entity/API adapter: wire DTO→`RagInstance`, `PipelineCandidate`, `Citation`, `AnswerArtifact` 매핑.
- Shared UI: API·router·domain store를 import하지 않는 props-only presentation.
- PDF/Evidence viewer와 큰 answer renderer는 lazy load한다. Output 오류가 composer와 Context를 멈추게 하지 않는다.

## 6. 접근성·포커스·AI 상태

### keyboard 흐름

Desktop DOM 순서는 `Global nav → Context → Work → Output`을 따른다. 시각 순서와 다르게 CSS order로 재배치하지 않는다.

1. 문서 범위 checkbox를 Space로 바꾸고, 별도 `문서 열기` button을 Enter로 연다.
2. composer에 질문을 입력하고 Enter(IME 조합 중 제외) 또는 `질문하기`로 보낸다.
3. 비교에서는 후보 checkbox를 선택하고 citation/원본 보기/다음 라운드/완료 순으로 이동한다.
4. citation에서 EvidenceDrawer를 열면 heading에 focus, Escape/닫기 시 citation으로 restore한다.
5. confirm dialog는 `다시 비교하기`부터 focus하고 Tab이 dialog 밖으로 나가지 않는다.

### live region과 상태 문구

- 스트리밍 답변 본문 전체를 `aria-live`로 두지 않는다. `조항 단위 · 일반 검색 답변 생성 중`, `답변 생성 완료`만 `role=status`/`aria-live=polite`로 알린다.
- processing에는 백엔드가 제공한 실제 `stage`, `completed`, `total`, `message`, `updatedAt`만 쓴다. 클라이언트 타이머로 진척률을 꾸며내지 않는다.
- 근거 부족은 오류가 아니라 verification 결과다. `근거를 찾지 못함` heading, 검색 범위/질문 변경 CTA, citation 없음으로 렌더한다.
- icon-only control에는 한국어 `aria-label`과 tooltip이 모두 필요하다. tooltip은 focus에서도 표시한다.

### 최소 테스트 세트

| 분류 | 반드시 자동/수동 확인할 시나리오 |
|---|---|
| Component | button focus/disabled/loading, candidate 6개 상태, composer IME/error/generating, citation focus/open, dialog focus restore |
| Integration | 문서 선택→질문→SSE generating→stop/retry→citation open→panel restore, 동점→확정 불가→확정 확인 |
| Responsive | 1440×1024, 1280×800, 1024×768, 768×1024, 390×844 |
| A11y | keyboard-only, axe, 200% zoom, reduced motion, high contrast, screen-reader smoke test |
| Visual | dashboard empty/ready/processing, setup upload/partial/error, compare streaming/no-evidence/failed, detail evidence drawer, mobile drawer |

## 7. 프론트엔드 적용 우선순위

### P0 — 다음 구현 단위에서 필수

1. `theme.ts`와 shared primitives를 토큰 기반으로 정리하고 action hover·status 의미를 교정한다.
2. global `min-width: 768px`를 제거하고 desktop/tablet/mobile breakpoint와 shell 전환을 만든다.
3. `DocumentScopeItem`을 checkbox + open button의 sibling 구조로 재구성한다. 중첩 interactive 금지.
4. `EvidenceDrawer`/`FinalizationDialog`에 focus trap, Escape, restore, `aria-modal`, responsive drawer를 적용하고 실제 citation을 전달한다.
5. dashboard/detail/setup의 empty/error/retry/partial states와 candidate `preparing | streaming | failed` 상태를 mock fixture에서 먼저 제공한다.

### P1 — workspace 신뢰성 완성

1. 상세/비교에 Context–Work–conditional Output shell, panel header, scroll ownership을 적용한다.
2. `SearchModeSelect`, `SensitivityControl`, `RagStepProgress`, `AnswerComposer`, `AsyncStatePanel`을 shared component로 추출한다.
3. SSE stream/stop/retry와 job polling을 UI 상태 계약대로 연결한다. 기존 결과는 refresh 중 유지한다.
4. 질문 설정의 radio card focus/설명 연결 및 도움말 popover를 구현한다.

### P2 — 결과물 관리·고도화

1. AnswerArtifact/최근 답변 Output panel, copy/retry/open 관리 흐름을 추가한다.
2. URL에 active tab/evidence를 반영하고 panel rail/collapse preference를 저장한다.
3. lazy evidence viewer, panel ErrorBoundary, visual regression 및 axe CI를 추가한다.

## 8. v2 완료 수용 기준

- [ ] 각 route가 Context/Work/Output 중 어떤 역할을 쓰는지 설명할 수 있으며, 대시보드·설정에 불필요한 3패널을 강제하지 않는다.
- [ ] 1440px에서 상세은 Work 최소 폭을 유지한 채 Context와 Evidence Output을 병렬로 볼 수 있다.
- [ ] 1024px에서는 Output이 drawer, 768px 이하에서는 Context와 Output 모두 단일 작업을 방해하지 않는 drawer/route로 동작한다.
- [ ] 390px에서 가로 스크롤과 `min-width` 차단 없이 문서 범위 선택, 질문, 인용 열기, 비교 후보 선택을 마칠 수 있다.
- [ ] panel마다 하나의 scroll owner가 있으며 composer/action bar가 답변 위를 덮지 않는다.
- [ ] checkbox·open·menu 등 독립 행동이 중첩되지 않고 keyboard-only로 작업을 완료할 수 있다.
- [ ] dialog/drawer는 열기·Escape·닫기에서 focus를 올바르게 trap/restore한다.
- [ ] processing·streaming·partial failure·no evidence·offline·permission denied의 화면이 mock과 실제 API 모두에서 재현된다.
- [ ] loading/refresh 중 기존 콘텐츠의 폭·높이·scroll position이 불필요하게 초기화되지 않는다.
- [ ] status는 색상뿐 아니라 아이콘과 텍스트로 읽히고, live region이 답변 토큰을 반복 낭독하지 않는다.
- [ ] 새로운 스타일 값은 역할 토큰으로만 추가되며, CSS token·styled theme·component 간 의미가 일치한다.
- [ ] v2 최소 테스트 세트가 build/test 및 수동 viewport/a11y 체크로 통과한다.

## 9. Skill review 체크 결과

| 항목 | 현재 | v2 후 목표 |
|---|---|---|
| 핵심 Work 우선 | 부분 충족 | Work 최소 폭·stable geometry 보장 |
| 현재 Context 가시성 | 부분 충족 | 문서 범위/조건이 모든 workspace 상태에서 유지 |
| Output 객체화 | 미충족 | 근거와 답변 기록을 열고 재확인 가능 |
| Scroll ownership | 미충족 | 패널별 단일 owner 명시 |
| Mobile 단일 작업 | 미충족 | drawer/route로 전환 |
| 상태 행렬 | 부분 충족 | candidate/composer/panel/output 전 상태 구현 |
| Verification first-class | 부분 충족 | 실제 citation→segment, focus-safe EvidenceDrawer |
| token-only styling | 미충족 | theme mapping 및 raw 값 제거 |
| keyboard/accessibility | 부분 충족 | nested interaction 제거, dialog lifecycle 완성 |

이 문서의 목적은 NotebookLM의 고유 화면을 복사하는 것이 아니라, RAG Portal이 가진 “문서 범위에서 답을 만들고 근거를 검증한다”는 작업을 가장 명료하게 만드는 것이다.
