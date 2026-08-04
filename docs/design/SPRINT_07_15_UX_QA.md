# Sprint 07–15 UX/QA 리뷰 — 작업을 잃지 않는 RAG Workspace

> 감사일: 2026-08-03  
> 범위: 생성 → 준비/비교 → 검색/근거 → job·재파싱·재튜닝·후보 탐색  
> 기준: NotebookLM-inspired `Context → Work → Output`, Core Work First, Visible System Status, Reversible Exploration, Outputs Are Objects

## 판정

데스크톱의 기본 Workspace는 의도에 맞다. 앱 셸과 LNB, 1440px 이상 상세 화면의 Context/Work/Output은 각각 스크롤 소유권을 갖고, 채팅과 composer는 분리되어 있으며, 390px에서는 Work를 먼저 보여 주고 패널을 교대한다. 후보 카드의 준비 상태, Evidence focus 복귀, job 재시도, 원본 provenance, 재튜닝의 명시적 시작도 구현되어 있다.

초기 리뷰에서 확인한 **721–1380px drawer 상태**, **재파싱 직후 오래된 문서 선택**, **실제 중단과 화면 표시 중단의 차이** P0는 후속 프런트 보완에서 해결·회귀 테스트됐다. Sprint 12–15의 기능을 우측 `설정` 탭에 계속 쌓는 구조는 여전히 P1 정보 구조 개선 항목이다.

후속 검증에서 `npm test -- --run`은 2026-08-03에 6 files / 28 tests를 통과했고 1280px·800px drawer 상태와 재파싱 선택 해제도 회귀로 포함됐다. 실제 브라우저의 시각·스크롤 검증은 여전히 필요하다.

## 현재 확인하여 유지할 것

| 영역 | 확인한 상태 | 유지 이유 |
| --- | --- | --- |
| 앱 셸과 LNB | `AppShell`이 화면 높이를 소유하며 desktop LNB와 일반 본문은 독립 `overflow-y:auto` | 긴 목록과 본문에서 위치를 서로 빼앗지 않음 |
| 1440px 이상 상세 | Context, Work의 messages, OutputBody가 각자 scroll container | 근거를 보며 긴 답변을 읽는 병렬 작업에 적합 |
| 채팅/작성 영역 | message 영역의 하단 여백과 composer의 border·간격이 분리됨 | 이전 답변과 다음 질문이 시각적으로 섞이지 않음 |
| 모바일 기본 진입 | 390px에서는 Context/Output이 닫히고 Work를 우선 노출 | 데스크톱 3패널을 축소하지 않음 |
| 상태와 복구 | 후보 준비 상태, job retry, full-reindex 차단 사유, fallback 고지 | 가짜 진행률이나 숨은 전제조건을 줄임 |

## 해결됨 — P0 작업 단절

### 해결됨 P0-1. 721–1380px에서 기본으로 열린 drawer가 Core Work를 덮는다

**재현**

1. `/rag/:id`를 1280px 또는 800px 폭에서 새로 연다.  
2. `RagDetailWorkspace`의 초기 `open` 상태는 720px 초과에서 `{ context: true, output: true }`다.  
3. CSS는 1380px 이하에서 Output을 fixed drawer로, 1024px 이하에서 Context와 Output을 모두 fixed drawer로 바꾼다. 두 패널은 그 폭에서 자동으로 닫히거나 상호 배타적으로 바뀌지 않는다.

**영향**

- 1280px에서는 기본 Output drawer가 질문/답변 폭 위를 덮고, 768–1023px에서는 좌·우 drawer가 동시에 Work를 거의 전부 덮거나 서로 겹친다.
- 같은 폭에서 두 영역이 모두 `aria-modal` dialog가 될 수 있어, “한 번에 한 작업”이라는 모바일/태블릿 원칙과 키보드 순서가 깨진다.

**프런트 핸드오프**

- breakpoint를 상태 모델에도 반영한다. `>= 1380: context + work + output`, `1024–1379: context + work, output closed drawer`, `721–1023: work only, context/output closed and mutually exclusive`, `<=720: work only`로 고정한다.
- resize 시 현재 열려 있는 두 drawer를 정규화하고, 열어 준 버튼으로 focus를 돌린다. 단순 CSS `display` 전환에 상태를 맡기지 않는다.
- drawer를 modal로 유지할 경우 backdrop와 `inert`/focus trap을 제공한다. 보조 패널로 유지할 경우 `aria-modal`을 제거하고 Work를 가리지 않는 rail/inline 모델로 바꾼다. 둘을 섞지 않는다.

**수용 증거**

- Playwright/visual regression: 1440, 1280, 1024, 800, 390px에서 첫 화면의 검색 input과 `질문하기`가 보이고 keyboard focus 가능하다.
- 800px에서 Context를 열면 Output은 닫히고, Output을 열면 Context는 닫힌다. Escape 뒤에는 열었던 toggle로 focus가 복귀한다.
- 1280px에서 긴 답변 스크롤 중 Output을 열고 닫아도 Work의 scrollTop과 draft가 보존된다.

### 해결됨 P0-2. 재파싱은 즉시 기존 검색 선택을 무효화하고, 영향 확인 뒤 시작해야 한다

**재현**

1. 확정·검색 가능한 문서 A/B를 모두 Context에서 선택하고 질문 draft를 입력한다.  
2. Output → `문서` 탭에서 A의 `원본 다시 읽기`를 누른다.  
3. backend는 A의 finalized candidate를 제거하고 `REPARSE` job을 시작한다. 그러나 `reparseDocument()` 직후 프런트는 `selectedIds`를 정리하지 않고 상세 route에도 남아 있다.

**영향**

- A는 비활성 checkbox가 되었어도 이전 선택 상태가 잠시 남을 수 있다. B가 준비되어 있으면 사용자는 A+B 범위로 질문을 보내 `DOCUMENT_NOT_FINALIZED`를 만날 수 있다.
- “원본 다시 읽기”는 후보/검색 준비를 교체하고 재비교가 필요할 수 있는 고영향 행동인데 확인 대화와 작업 후 다음 단계가 없다. 사용자는 설정 탭에 머문 채 왜 검색이 멈췄는지 찾아야 한다.

**프런트/API 핸드오프**

1. reparse accepted 응답에 `invalidated_document_ids`, job id, `next_action: TUNE_DOCUMENT`를 확정 계약으로 두고 즉시 선택에서 제외한다. 기존 draft와 다른 준비 완료 문서의 선택은 보존한다.
2. 시작 전 confirmation에 문서명, 현재 검색에서 제외됨, 기존 후보/설정은 baseline artifact로 보존됨, 완료 뒤 다시 비교 필요를 평이한 문장으로 보여 준다. 기본 focus는 `취소`다.
3. 확인 뒤에는 Work 상단에 작은 작업 banner를 남긴다: `A를 다시 읽고 있어요 · 검색 범위에서 제외됨 · 작업 상태 보기`. 완료/실패 시 `비교 이어가기` 또는 `다시 시도`를 직접 제공한다.

**수용 증거**

- A/B 선택 상태에서 A 재파싱 직후 A는 unchecked·unavailable, B와 draft는 유지된다. search request에는 B만 포함된다.
- confirmation 취소 시 API 호출/선택/route가 바뀌지 않는다. 확인 시 REPARSE job id와 baseline artifact가 표시 가능한 작업 객체로 남는다.
- 새로고침·대시보드 왕복·실패/취소/재시도 후에도 A의 `재비교 필요` 상태와 다음 행동이 동일하다.

### 해결됨 P0-3. “중단”의 실제 범위를 서버 계약과 화면 문구가 끝까지 일치시켜야 한다

**관찰**

현재 UI는 정직하게 `이 화면의 답변 표시를 중단했어요. 서버 작업은 계속될 수 있어요.`라고 설명한다. 그러나 사용자는 버튼에서 작업 취소를 기대하기 쉽고, prior Sprint 07–10 audit에서 확인한 것처럼 stream endpoint는 생성 완료 뒤 토큰을 보내는 구조라 실제 진행/취소와 다르다.

**프런트/백엔드 핸드오프**

- 버튼을 정책에 맞게 분리한다. 서버 취소가 지원되기 전에는 `표시 중단`으로 명명하고, 지원 후에만 `생성 중단`을 사용한다.
- 서버가 계속하는 경우 Output의 `최근 작업`/답변 artifact에 `백그라운드 완료 여부 보기`를 연결한다. 사용자가 같은 질문을 다시 보내기 전에 이전 결과를 열 수 있어야 한다.
- 서버 취소를 구현하면 disconnect/cancel signal, terminal `CANCELLED`, artifact 정책(미생성 또는 취소 객체), 재시도 범위를 하나의 계약으로 테스트한다.

**수용 증거**

- 지연된 generator에서 버튼 라벨, 화면 상태, artifact 최종 상태가 모두 같은 정책을 말한다.
- 화면 이탈·새로고침 후에도 표시 중단 요청의 서버 결과를 확인할 수 있고, 중복 질문이 자동으로 발생하지 않는다.

## P1 — P0 이후의 흐름·정보 구조 개선

### P1-1. `설정`에 운영·재튜닝·기술 메타데이터를 함께 쌓지 않는다

**재현/관찰**

Output의 `설정` 탭(폭 17.5–21rem)은 developer runtime gate, fallback 설명, 문서 작업 상태/이력, 재튜닝 신호/전후 상태, 읽기 전용 스펙을 한 스크롤에 표시한다. 일반 사용자는 `재튜닝 시작`을 찾으려면 런타임과 운영 상태를 지나야 하고, 개발자 정보와 자신의 다음 행동이 동등한 밀도로 경쟁한다.

**권고**

- Output을 `근거 | 문서 | 작업`으로 재구성한다. `작업`에는 현재 job, 재시도, 재파싱, 재튜닝과 다음 행동만 둔다. 모델 runtime/queue detail은 권한 있는 `환경 점검` disclosure로 낮춘다.
- 재튜닝 추천은 검색 결과 피드백 뒤 또는 Header의 비차단 notice로도 보이게 하되, 시작 전에 대상 문서·기준·검색 중단 영향·baseline 보존을 확인한다.
- 작업 이력은 최대 3개 요약 + `전체 이력`으로 progressive disclosure하고, 상태가 없는 설정 탭에는 빈 운영 카드 대신 읽기 전용 설정만 보인다.

**QA**

- 360px drawer와 1440px side panel에서 첫 viewport에 현재 작업 상태, 원인, primary recovery CTA가 함께 보인다.
- 재튜닝 권장/미권장/실행 중/실패 fixture에서 사용자용 문구에 endpoint, queue, provider 원문이 노출되지 않는다.

### P1-2. 재튜닝과 후보 탐색을 “기능 카드”가 아니라 되돌아갈 수 있는 작업 객체로 연결한다

**관찰**

- retune은 baseline/outcome artifact를 저장하지만 UI는 `결과 기록됨` 텍스트만 보이고, 이전 기준·새 비교·최종 선택을 다시 열 수 없다.
- 후보 탐색은 기본 비교 화면 상단에 항상 큰 notice와 `후보 탐색 제안 만들기`를 표시한다. 첫 라운드의 핵심 행동인 질문 비교/후보 선택보다 고급 행동이 먼저 노출된다.
- proposal/rollback/restore 뒤에는 목록과 status 문구만 보이며, 무엇이 추가·보관·복원됐고 현재 후보 풀에 어떤 영향을 줬는지 한 곳에서 추적하기 어렵다.

**권고**

1. Artifact drawer 또는 `작업` 탭에 `재튜닝 기준`, `새 후보 비교`, `확정 결과`, `후보 탐색 제안`을 타입·시각·문서 범위·상태·열기 행동으로 나열한다. 답변 artifact도 같은 모델에 포함한다.
2. 탐색은 기본적으로 `후보 비교 도움말` disclosure 안에 숨기고, 근거 부족/동점/명시적 사용 요청 때만 권장한다. 시작 뒤에는 parent 후보, parameter/retrieval delta, evidence boundary, rollback 영향을 표로 보인다.
3. rollback/restore에는 confirmation과 결과 요약을 둔다. 후보를 자동 선택·확정하지 않는 현재 원칙은 유지한다.

**QA**

- 새로고침 뒤 baseline → outcome → finalized artifact를 순서대로 열고 각각의 문서/근거로 이동할 수 있다.
- exploration을 만들고 rollback/restore한 뒤 원래 후보의 투표·확정은 변하지 않으며, UI가 그것을 문장으로 확인한다.
- 첫 비교 라운드에서는 후보 탐색이 primary CTA가 아니며, 한 문맥에 primary CTA가 하나다.

### P1-3. Evidence는 citation마다 같은 깊이로 원문 검증을 제공한다

**관찰**

채팅의 citation 번호는 최소 24px에 가깝고 Output으로 focus를 옮긴다. 다만 `openEvidence()`는 처음 연 citation의 `navigateUrl`만 lazy-load한다. Evidence 목록에서 다른 citation을 고르면 해당 citation의 원문 위치를 다시 읽지 않으며, `원문 위치 열기` 행동도 없다.

**권고**

- citation 선택을 단일 source of truth로 두고, 선택이 바뀔 때마다 해당 citation을 lazy-load한다.
- PDF page, DOCX heading, CSV/XLSX row처럼 위치를 type-specific하게 보이고 `원문 위치 열기`, 이전/다음 citation, 닫기와 trigger focus 복귀를 제공한다.
- 다문서 답변은 선택 문서 수와 실제 근거 기여 문서를 구분한다. 인용 0개 문서는 “근거에 사용되지 않음”으로 명시한다.

**QA**

- 같은 문서의 두 citation과 서로 다른 두 문서를 키보드로 순회하며 각각의 원문 preview/위치를 검증한다.
- 화면 폭 800px에서 Evidence drawer를 열어도 Work draft와 메시지 scroll position은 바뀌지 않는다.

### P1-4. 지원 폭에서도 LNB·Work·Output의 스크롤 정책을 명시적으로 회귀 테스트한다

**관찰**

1440px에서는 독립 scroll이 구현돼 있다. 하지만 1380px 이하에서 `AppShell Main`이 다시 outer scroll을 소유하고 fixed drawer가 섞인다. 긴 후보 비교/문서 관리/작업 이력에서는 어느 영역이 움직이는지 폭과 콘텐츠 길이에 따라 달라질 수 있다.

**권고**

- breakpoint별 scroll owner를 문서와 CSS 테스트에 고정한다: desktop은 `LNB / Context / Messages / Output` 독립, tablet은 `Main + 하나의 modal drawer`, mobile은 `Main/Work + 하나의 modal drawer`.
- 고정 action bar, bottom drawer, iOS safe area에 `env(safe-area-inset-bottom)`을 반영한다. setup의 action bar가 마지막 후보/CTA를 가리지 않아야 한다.

**QA**

- 100개 문서 Context, 30개 citation, 12개 job history fixture에서 각 scroll container의 wheel/keyboard scroll이 이웃 패널을 움직이지 않는다.
- 1280px의 비교 sticky bar와 390px의 bottom drawer에서 마지막 interactive element가 가려지지 않는다.

### P1-5. hover/title 전용 설명을 접근 가능한 도움말로 바꾼다

**관찰**

후보 카드의 `?`와 일부 정밀 검색 설명은 `title`에만 상세 내용을 넣는다. `aria-label`은 “설명”이라고만 읽어 주므로 키보드/스크린리더 사용자는 실제 설명을 얻지 못한다. setup의 citation chip은 22px이라 최소 24px citation target 기준에도 못 미친다.

**권고**

- `?`를 button + focusable popover 또는 항상 보이는 짧은 보조 문구로 바꾸고 `aria-expanded`, `aria-controls`, Escape/focus return을 제공한다.
- citation/compact icon target을 최소 24px(가능하면 공통 44px)로 맞춘다. 색만으로 READY/FAILED/NO_EVIDENCE를 전달하지 않는 현재 문구·아이콘은 유지한다.

**QA**

- mouse 없이 후보 설명을 열고 닫으며 같은 카드의 checkbox로 돌아올 수 있다.
- axe + keyboard smoke에서 tooltip/title에 의존하는 핵심 정보가 없고, 200% zoom에서도 chip/CTA가 겹치지 않는다.

## P2 — 다음 제품화 단계

| 항목 | 이유 | 핸드오프 |
| --- | --- | --- |
| Dashboard 작업 재개 카드 | processing/retune/reparse 상태에서 카드 CTA가 모두 `열기 →`라 다음 단계가 약하다 | `이어서 비교`, `작업 상태 보기`, `재튜닝 검토`를 상태별로 구분하고 background job 완료 뒤 목록을 refresh |
| Skip link와 landmark 이름 | LNB가 독립 scroll인 만큼 keyboard 사용자는 매 route마다 nav를 통과한다 | `본문으로 건너뛰기`, page-specific main/aside label, 현재 route 제목을 추가 |
| 답변 이력과 질문 재사용 | 현재 Work는 세션의 최근 답변 위주라 새로고침/이탈 뒤 비교 맥락이 사라진다 | artifact 목록에서 질문·문서 범위·민감도·fallback·근거를 열고 `같은 조건으로 다시 검색` |
| 긴 대화의 읽기 보조 | history가 도입되면 작성 영역과 최신 답변 위치를 쉽게 찾아야 한다 | 사용자가 위로 충분히 읽었을 때만 `최신 답변으로` pill을 표시; 자동 scroll은 하지 않음 |

## 권장 구현 순서와 담당 경계

1. **Frontend + QA — P0-1**: breakpoint state machine, drawer semantics, 1440/1280/1024/800/390 visual test.
2. **Frontend + Backend + QA — P0-2**: reparse accepted payload/선택 정규화/confirmation/작업 banner와 A/B multi-document E2E.
3. **Backend + Frontend + QA — P0-3**: stream cancel/artifact 정책을 정하고 UI 라벨·결과 확인을 일치.
4. **Designer + Frontend — P1-1/2**: Output을 작업 객체 중심 정보 구조로 재배치하고 retune/exploration confirmation·artifact navigation을 설계.
5. **Frontend + QA — P1-3/4/5**: citation viewer, scroll ownership, safe-area, keyboard help regression.

## 완료 정의

- [ ] 어떤 지원 폭에서도 Work의 질문 입력과 primary CTA가 기본적으로 보이며 drawer는 하나만 열린다.
- [ ] 재파싱·재튜닝·후보 탐색을 시작할 때 영향, 되돌림 가능성, 다음 행동이 시작 전과 후에 모두 보인다.
- [ ] job/answer/retune/exploration 결과가 새로고침 후에도 열 수 있는 객체로 남는다.
- [ ] LNB, Context, messages, Output의 scroll owner가 breakpoint별로 문서화되고 자동 회귀된다.
- [ ] 근거는 citation마다 원문 위치까지 키보드로 검증 가능하다.
- [ ] 비전문가의 기본 비교/검색 흐름은 runtime·queue·고급 탐색 정보보다 먼저 보이며, 한 문맥의 primary action은 하나다.
