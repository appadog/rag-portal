# Enterprise RAG `Frontend` 상세 설계

## 1. 목적과 범위

Enterprise RAG Frontend는 사용자가 채팅, 문서·지식 관리, 지식 생성 전략 선택, 품질 평가와 업무 운영 상태를 하나의 Web UI에서 이용하도록 하는 사용자 상호작용 컴포넌트이다.

본 문서는 다음을 상세화한다.

- Chat, Knowledge Management, Knowledge Strategy Selection, Quality Evaluation과 Operations 화면 책임
- 외부 인증 세션과 Backend 요청 컨텍스트 전달
- 화면·사용자 Operation 상태와 복구
- RAG Runtime, Knowledge Processing, Knowledge Strategy Selection, Quality Evaluation과의 상호작용
- 스트리밍 답변, 장시간 문서 처리와 평가 실행의 UI 상태
- Citation, 오류와 접근성 표현 원칙

UI Framework, Route 경로, 디자인 시스템, Backend API 경로와 배포 제품은 정의하지 않는다.

### 1.1 초기 구현 기준

- 하나의 Frontend 애플리케이션 안에서 기능 영역을 구분한다.
- Backend별 주소를 직접 노출하지 않고 공통 외부 요청 경계를 사용한다.
- 사용자 인증과 조직 권한 판정은 외부 시스템이 담당한다.
- Tenant 격리의 최종 책임은 Backend에 있으며 Frontend 필터링만 신뢰하지 않는다.
- Chat 답변은 Answer와 Citation을 함께 이해할 수 있게 표시한다.
- 장시간 문서 처리와 평가 실행은 요청 수용과 완료를 분리해 표현한다.
- 외부 모니터링 대시보드를 Frontend Operations 화면에 복제하지 않는다.

---

## 2. 책임과 경계

### 2.1 핵심 책임

- 검증된 사용자 세션 상태 수용
- 현재 Tenant와 사용자 참조 표현
- Backend 요청에 필요한 사용자·Tenant·추적 맥락 전달
- 채팅, 스트리밍 답변, 이력과 Citation 표시
- 사용자 피드백 입력
- Knowledge Base·문서 등록, 상태, 실패와 재처리 화면
- 최초 지식 생성 전 후보 전략 결과 비교, 선택과 최종 확정 화면
- 시스템 공통 외부 자원 관리 화면
- 평가 Dataset·Run·Result 화면
- 선택적 자원 구성 비교 평가 화면
- 업무 처리 상태와 재처리 대상 화면
- 로딩·빈 결과·부분 성공·오류·재시도 상태 표현
- 접근 가능한 사용자 상호작용 제공

### 2.2 입력과 출력

| 구분 | 주요 정보 |
|---|---|
| 입력 | 외부 인증 세션, Tenant·Subject, Backend 업무 결과, 스트리밍 조각, 상태·오류·Citation·평가 결과 |
| 출력 | 사용자 Operation, 질문, 문서·평가 입력, 피드백, 조회·재처리·취소 요청, 화면 상태와 추적 가능한 요청 맥락 |

### 2.3 소유하는 판단과 상태

- 현재 화면과 사용자 입력의 Client State
- 요청 제출·대기·완료·실패의 Client Operation State
- 화면에 표시할 선택·정렬·필터·확장 상태
- 중복 제출 방지를 위한 Client Request 상태
- 사용자에게 표시할 오류·진행·완료 Feedback

Frontend는 Backend 업무 상태와 권한을 소유하지 않으며 응답 결과를 화면 상태로 투영한다.

### 2.4 의존하는 책임

- 외부 인증 시스템: 사용자 인증, 세션과 관리 기능 접근 통제
- RAG Runtime: 대화·질문·Answer·Citation
- Knowledge Processing: Knowledge Base·문서·처리·게시 상태
- Knowledge Strategy Selection: 후보·비교 실행·사용자 선택·최종 확정 상태
- Quality Evaluation: Feedback·Dataset·Run·Result·Comparison
- Resource Manager: 시스템 공통 외부 자원 프로파일과 적용 구성
- 외부 모니터링 시스템: 시스템 관찰정보의 분석·시각화·경보

### 2.5 수행하지 않는 역할

- 인증 Token 발급과 사용자·조직 권한 판정
- Tenant 데이터 격리의 최종 강제
- 지식 구성·검색·답변과 품질 평가 실행
- Backend 업무 상태의 임의 생성·변경
- 모델·검색 저장소·프롬프트 직접 호출
- OpenTelemetry 데이터 장기 저장·분석·경보
- Client에 Secret 또는 외부 자원 연결정보 저장

---

## 3. 내부 구성

### 3.1 내부 모듈

| 내부 모듈 | 주된 책임 |
|---|---|
| Application Shell | 화면 영역, Navigation과 공통 Layout |
| Session Context | 외부 인증 세션과 현재 Tenant·Subject 맥락 수용 |
| Request Context | Request·멱등성·Trace 맥락 생성·전달 |
| Backend Interface | 각 Backend와의 상호작용과 오류 정규화 |
| Chat Experience | Conversation, 질문, 스트리밍 Answer와 Citation |
| Knowledge Experience | Knowledge Base, 문서 등록·상태·재처리 |
| Strategy Selection Experience | 후보별 답변·Citation·원문 근거 비교, 선택과 최종 확인 |
| Resource Management Experience | 시스템 공통 외부 자원 구성 관리 |
| Quality Experience | Feedback, Dataset, Run, Result와 Comparison |
| Operations Experience | 업무 처리 상태·실패·재처리 대상 조회 |
| Client State Management | 화면·사용자 Operation 상태와 복구 |
| Presentation & Accessibility | 일관된 표현, 키보드·보조기술·반응형 접근 |
| Frontend Observability | Client 오류·성능·요청 연계 관찰정보 |

### 3.2 내부 의존 방향

```text
Application Shell
        ↓
Session Context
        ↓
Chat · Knowledge · Resource Management · Quality · Operations Experience
        ↓
Client State Management
        ↓
Backend Interface
        ↓
Request Context

모든 화면 모듈
        ↓
Presentation & Accessibility
        ↓
Frontend Observability
```

화면 모듈은 다른 화면 모듈의 내부 상태에 직접 의존하지 않고 공유가 필요한 식별 참조만 전달한다.

### 3.3 상태 변경 책임

| Client 상태 | 변경 책임 |
|---|---|
| Session View | Session Context |
| Navigation·공통 Layout | Application Shell |
| Chat View·Draft·Stream | Chat Experience |
| Knowledge View·Upload | Knowledge Experience |
| Resource Management View | Resource Management Experience |
| Quality View·Evaluation Progress | Quality Experience |
| Operations View | Operations Experience |
| 공통 Request 상태 | Client State Management |

Backend 업무 상태는 Backend 응답을 통해서만 변경된 것으로 반영한다.

### 3.4 내부 Operation 명세

| Operation | 제공 모듈 | 목적 |
|---|---|---|
| ResolveSessionContext | Session Context | 현재 사용자·Tenant 참조 제공 |
| CreateClientRequestContext | Request Context | 요청·멱등성·Trace 맥락 구성 |
| ExecuteBackendOperation | Backend Interface | Backend 요청·응답과 오류 정규화 |
| ManageChatInteraction | Chat Experience | 질문·스트리밍·Citation 상호작용 |
| ManageKnowledgeInteraction | Knowledge Experience | 문서·처리 상태 상호작용 |
| ManageResourceInteraction | Resource Management Experience | 시스템 공통 외부 자원 관리 상호작용 |
| ManageQualityInteraction | Quality Experience | Feedback·평가 상호작용 |
| ManageOperationsInteraction | Operations Experience | 업무 상태·재처리 상호작용 |
| PresentAccessibleState | Presentation & Accessibility | 상태와 결과의 접근 가능한 표현 |

---

## 4. 핵심 정보 모델

### 4.1 정보 정의

| 정보 | 의미 |
|---|---|
| Session View | 외부 인증 결과에서 Frontend가 사용할 사용자·Tenant 참조 |
| Client Request Context | 하나의 사용자 Operation을 추적·중복 방지하는 맥락 |
| Client Operation | 제출·조회·재처리 같은 사용자 행위의 Client 실행 상태 |
| Conversation View | Conversation과 Message의 표시 모델 |
| Answer View | 스트리밍·완료·제한·실패 Answer의 표시 모델 |
| Citation View | Answer와 원본 위치를 탐색하는 표시 모델 |
| Knowledge View | Knowledge Base·Document·Version·처리 상태 표시 모델 |
| Upload Draft | 사용자 선택 파일과 입력 Metadata의 제출 전 상태 |
| Evaluation View | Dataset·Run·Case·Metric·Comparison 표시 모델 |
| Feedback Draft | 사용자가 작성 중인 평가 입력 |
| Operation View | Backend 업무 처리 상태·실패·재처리 가능성 표시 모델 |
| UI Error | 사용자 조치 가능성과 추적 참조를 포함한 오류 표시 모델 |

### 4.2 정보 관계

```text
Session View
  └─ Client Request Context
      └─ Client Operation
          ├─ Conversation View
          │   ├─ Answer View
          │   └─ Citation View
          ├─ Knowledge View
          │   └─ Upload Draft
          ├─ Evaluation View
          │   └─ Feedback Draft
          └─ Operation View
```

### 4.3 불변 규칙

- 현재 Tenant가 바뀌면 이전 Tenant의 화면 데이터와 Draft를 재사용하지 않는다.
- Backend에서 확인하지 않은 Tenant·대화 소유권과 업무 상태를 성공으로 표시하지 않는다.
- Answer 완료와 스트리밍 중 상태를 구분한다.
- Citation은 해당 Answer가 반환한 출처 참조만 표시한다.
- 제한 응답을 일반 성공 답변과 시각적으로 구분하되 오류로 오인시키지 않는다.
- Client Request Context의 멱등성 참조는 Tenant가 바뀌면 재사용하지 않는다.
- Upload Draft의 파일 원문을 불필요하게 장기 Client 저장소에 보존하지 않는다.
- 오류 화면에 Token, Secret, 내부 Endpoint와 원문 Prompt를 표시하지 않는다.

### 4.4 구현용 논리 필드

| 정보 | 필수 의미 |
|---|---|
| Session View | Subject 표시 참조, Tenant 참조·표시명, 허용 기능, 만료·갱신 상태 |
| Client Operation | Operation 유형, 대상 참조, 상태, Request 참조, 시작·종료 시점, 오류 |
| Conversation View | Conversation 참조, Message 목록·순서, 추가 조회 상태 |
| Answer View | Query 참조, Stream 상태, 내용, Answer 상태, Citation 목록 |
| Knowledge View | Knowledge Base·Document·Version 참조, 처리·게시 상태, 실패 요약 |
| Evaluation View | Dataset·Run 참조, 진행률, Case·Metric 결과와 선택적 자원 구성 비교 기준 |
| UI Error | 사용자 메시지, 재시도 가능 여부, 지원용 요청·Trace 참조 |

---

## 5. 상태와 생명주기

### 5.1 Client Operation 상태

```text
IDLE
  → SUBMITTING
  → ACCEPTED
  → IN_PROGRESS
  ├─ SUCCEEDED
  ├─ PARTIALLY_SUCCEEDED
  ├─ FAILED
  └─ CANCELLED
```

모든 Operation이 모든 상태를 사용하는 것은 아니다.

### 5.2 Chat Answer 화면 상태

```text
READY
  → SENDING
  → RECEIVING
  ├─ COMPLETED
  ├─ LIMITED
  └─ FAILED
```

- `RECEIVING`: 스트리밍 조각을 표시하지만 완료 Answer로 확정하지 않음
- `LIMITED`: 지식 범위에서 답할 수 없다는 정상적인 제한 결과
- `FAILED`: 사용자가 재시도 또는 지원 요청을 판단해야 하는 기술·업무 실패

### 5.3 Upload 화면 상태

```text
DRAFT
  → VALIDATING
  → UPLOADING
  → ACCEPTED
  → PROCESSING
  ├─ AVAILABLE
  └─ FAILED
```

`ACCEPTED` 이후의 Backend 처리 상태는 조회·갱신 결과로 표시한다.

### 5.4 Evaluation 화면 상태

```text
CONFIGURING
  → STARTING
  → RUNNING
  → AGGREGATING
  ├─ COMPLETED
  ├─ PARTIALLY_COMPLETED
  ├─ FAILED
  └─ CANCELLED
```

### 5.5 금지되는 상태 전이

- Backend 수용 전 `SUCCEEDED` 표시
- 스트리밍 중 Answer를 `COMPLETED`로 저장
- Tenant 변경 후 이전 화면의 재처리·삭제 Action 실행
- 실패한 Upload를 같은 Client 요청으로 임의 완료 처리
- Dataset 검수 결과 없이 실행 가능 상태로 표시

새로고침 후에는 Backend의 현재 상태를 다시 조회해 Client 상태를 복원한다.

---

## 6. 주요 처리 흐름

### 6.1 세션 시작과 Tenant 변경

```text
Frontend 진입
  → 외부 인증 세션 확인
  → Session View 구성
  → 현재 Tenant와 허용 기능 확인
  → 초기 화면 데이터 요청
```

Tenant가 변경되면 다음을 수행한다.

- 진행 중 Client 요청의 처리 정책을 적용한다.
- 화면 Cache와 선택·Draft를 격리 또는 초기화한다.
- 새 Tenant Context로 Backend 데이터를 다시 조회한다.
- 이전 Tenant 데이터가 화면에 잔류하지 않는지 확인한다.

### 6.2 채팅

```text
Conversation 선택 또는 생성
  → 질문 Draft 작성
  → 중복 제출 방지 Context 생성
  → SubmitQuestion
  → 수용 상태 표시
  → 스트리밍 또는 진행 조회
  → Answer 완료·제한·실패 표시
  → Citation 표시와 원본 위치 탐색
  → 선택적 Feedback 제출
```

### 6.3 문서 등록과 처리 상태

```text
Knowledge Base 선택
  → 파일·Metadata 입력
  → Client 기본 검증
  → RegisterDocument
  → 수용된 Document Version 표시
  → 처리 상태 조회 또는 갱신 수신
  → AVAILABLE 또는 FAILED 표시
  → 실패 시 재처리 가능 조건과 사유 표시
```

Client 검증은 사용자 편의를 위한 것이며 Backend 검증을 대체하지 않는다.

### 6.4 지식 생성 전략 선택

```text
선택 기능 진입
  → 후보 준비 상태 표시
  → 비교 질문 입력
  → 후보별 답변·Citation·원문 근거 표시
  → 사용자 후보 선택
  → 필요 시 추가 질문 비교
  → 최종 전략 확인과 확정
  → 전체 지식 생성 상태 표시
```

전략 선택 화면은 운영 채팅과 시각적·상태적으로 구분한다. Frontend는 후보 우열과 최종 확정 가능 여부를 자체 판정하지 않고 Backend 상태를 표시한다.

### 6.5 품질 평가

```text
Dataset 선택·관리
  → 평가 대상 조건 입력
  → StartEvaluation
  → Run 진행과 Case 상태 표시
  → 완료·부분 완료·실패 표시
  → Metric과 실패 Case 확인
  └─ 선택적 확장
      → 비교 대상 외부 자원 구성정보 선택
      → Comparison 결과 표시
```

품질 개선 결과를 자동 적용하는 Action은 제공하지 않는다.

### 6.6 Operations

- Knowledge Processing Job, Runtime 실행과 Evaluation Run의 업무 상태를 책임 Backend에서 조회한다.
- 실패 사유와 재처리 가능 여부를 업무 관점으로 표시한다.
- 시스템 성능·Trace·Metric·경보 분석은 외부 모니터링 시스템으로 연결할 수 있다.
- Operations 화면이 외부 모니터링 시스템을 대체하지 않는다.

### 6.7 새로고침과 네트워크 복구

- 수용된 Backend 업무 참조가 있으면 현재 상태를 다시 조회한다.
- 수용 여부가 불명확한 변경 요청은 같은 멱등성 참조로 결과를 확인한다.
- 조회 실패와 업무 실패를 구분한다.
- 스트리밍 연결이 끊기면 최종 Query 상태를 조회한다.
- 복구 후 중복 Message·문서 Version·Evaluation Run을 만들지 않는다.

---

## 7. 컴포넌트 Operation 명세

### 7.1 Backend 상호작용 매핑

| 화면 영역 | 대상 Backend | 주요 Operation |
|---|---|---|
| Chat | RAG Runtime | CreateConversation, GetConversation, SubmitQuestion, GetQueryResult |
| Chat Feedback | Quality Evaluation | SubmitFeedback |
| Knowledge | Knowledge Processing | CreateKnowledgeBase, RegisterDocument, GetDocument, GetProcessingStatus, RetryDocumentProcessing, WithdrawDocument |
| Knowledge Strategy Selection | Knowledge Strategy Selection | StartStrategySelection, GetStrategySelection, ExecuteCandidateComparison, SubmitCandidateSelection, ConfirmSelectedStrategy, CancelStrategySelection |
| Resource Management | Resource Manager | 시스템 공통 외부 자원 구성 관리 |
| Quality | Quality Evaluation | CreateEvaluationDataset, ReviewEvaluationDataset, StartEvaluation, GetEvaluationStatus, GetEvaluationResult, CompareEvaluationRuns, CancelEvaluation |
| Operations | 각 책임 Backend | 업무 상태·실패·재처리 관련 조회 및 허용된 Action |

### 7.2 공통 요청 규칙

- 외부 인증 세션의 전달 방식은 보안·API 명세를 따른다.
- Tenant, Request, Trace와 필요한 멱등성 맥락을 보존한다.
- 일반 사용자 요청은 외부 자원 구성정보를 선택하거나 조립하지 않는다.
- 변경 Operation은 중복 제출 방지와 결과 확인 수단을 가져야 한다.
- 오류는 사용자 조치 가능 여부와 지원용 식별정보를 분리해 표시한다.

### 7.3 응답 표시 규칙

- `accepted`와 `completed`의 의미를 구분한다.
- 부분 성공은 누락·실패 범위를 함께 표시한다.
- 제한 응답과 기술 실패를 구분한다.
- Backend 원문 오류를 그대로 노출하지 않는다.
- Citation은 문서명·위치 등 허용된 정보만 표시한다.

구체적인 Request·Response Schema와 오류 코드는 API 설계에서 정의한다.

---

## 8. 오류와 복구

### 8.1 오류 분류

| 분류 | 화면 처리 |
|---|---|
| 세션 오류 | 재인증 또는 세션 복구 안내 |
| Tenant·소유권·범위 오류 | 처리할 수 없는 Action 중단과 안전한 안내 |
| 입력 오류 | 해당 입력 위치에 수정 가능한 내용 표시 |
| 업무 상태 충돌 | 최신 상태 재조회와 Action 재판단 |
| 일시적 통신 오류 | 재시도·상태 확인 제공 |
| 장시간 처리 실패 | 실패 단계·요약과 허용된 재처리 Action 표시 |
| 부분 성공 | 완료 결과와 실패 범위를 함께 표시 |
| 알 수 없는 오류 | 안전한 메시지와 지원용 요청 참조 제공 |

### 8.2 복구 원칙

- 변경 요청 재시도 전 Backend 수용 여부를 확인한다.
- 사용자 입력 Draft는 민감정보 정책 범위에서만 일시 보존한다.
- 현재 Tenant와 대상 참조가 일치할 때만 Action을 복원한다.
- Backend가 완료한 결과를 Client 오류 때문에 취소된 것으로 표시하지 않는다.
- 화면 오류 Boundary가 다른 기능 영역의 상태까지 제거하지 않도록 한다.

### 8.3 스트리밍 오류

- 수신된 부분을 완료 Answer로 확정하지 않는다.
- Query Execution 참조로 최종 상태를 조회한다.
- 재전송과 새 질문 제출을 구분한다.
- Citation이 확정되지 않은 부분에는 임의 출처를 표시하지 않는다.

---

## 9. 동시성, 멱등성과 일관성

### 9.1 사용자 동시 Operation

- 같은 Draft의 중복 제출을 방지한다.
- 동일 문서에 대한 철회와 재처리를 동시에 활성화하지 않는다.
- 평가 Run 시작 중 설정 변경을 잠그거나 새 Draft로 분리한다.
- 다른 화면의 독립 조회는 병렬로 수행할 수 있다.

### 9.2 멱등성

- 변경 Operation마다 Client Request 참조를 생성·보존한다.
- 네트워크 재시도에서 동일 요청 참조를 재사용한다.
- 사용자가 내용을 변경하면 새 요청 참조를 사용한다.
- Tenant가 바뀌면 이전 멱등성 참조를 재사용하지 않는다.

### 9.3 Client와 Backend 일관성

- Backend 상태를 진실의 원천으로 취급한다.
- 낙관적 UI를 사용하더라도 실패 시 Backend 결과로 복원한다.
- Cache에 있는 업무 상태는 최신성 표시 또는 재조회 정책을 가진다.
- 식별 참조 없이 Client 목록 순서만으로 대상을 변경하지 않는다.

---

## 10. Tenant, 보안과 권한

### 10.1 외부 인증 경계

- Frontend는 외부 인증 체계가 제공하는 세션을 사용한다.
- 자체 사용자·비밀번호·조직 생명주기를 구현하지 않는다.
- Token 검증의 최종 Backend·Gateway 책임을 Client 검사로 대체하지 않는다.
- 세션 만료·갱신·로그아웃은 외부 인증 명세를 따른다.

### 10.2 Tenant 격리

- Tenant 전환 시 화면 데이터·Cache·Draft를 격리한다.
- URL이나 Client State의 Tenant 값만으로 접근 가능성을 판단하지 않는다.
- Backend가 반환한 대상 Tenant가 현재 Context와 다르면 표시하지 않고 오류 처리한다.
- Tenant별 사용자 선택과 최근 항목을 저장할 경우 별도 Namespace를 사용한다.

### 10.3 Client 민감정보

- Token과 Secret을 안전하지 않은 영구 Client 저장소에 보존하지 않는다.
- 문서 원문과 질문·Answer를 불필요하게 Browser Log·Telemetry에 남기지 않는다.
- HTML·Markdown·문서 미리보기는 안전한 Rendering 정책을 적용한다.
- 내부 Endpoint와 외부 자원 연결정보를 사용자에게 노출하지 않는다.

### 10.4 사용자 입력 안전성

- 파일 선택과 Metadata는 Backend 검증 전 신뢰하지 않는다.
- 생성 답변과 문서 콘텐츠를 실행 가능한 코드로 취급하지 않는다.
- Citation Link와 다운로드는 허용된 Backend 참조를 통해 제공한다.
- 자유 입력과 오류 메시지는 안전하게 Escape·Render한다.

---

## 11. 접근성과 관찰성

### 11.1 접근성

- 키보드로 주요 Navigation과 Action을 수행할 수 있어야 한다.
- Focus 이동과 Modal 종료가 예측 가능해야 한다.
- 스트리밍·진행률·오류 상태를 보조기술에 전달한다.
- 색상만으로 성공·실패·제한 상태를 구분하지 않는다.
- 표·Metric·Citation에 의미 있는 Label과 관계를 제공한다.
- 장시간 작업은 현재 상태와 다음 가능한 Action을 명확히 표시한다.

구체적인 준수 수준은 UI/UX 상세 기준에서 확정한다.

### 11.2 Frontend 관찰정보

- 화면 진입과 주요 사용자 Operation
- Backend 요청 지연과 실패 분류
- 스트리밍 연결·중단
- Client Rendering 오류
- 세션 만료와 Tenant 전환
- 성능 지표

사용자 입력 원문, 문서 내용, Answer와 Token은 기본 Telemetry에서 제외한다.

### 11.3 Trace 연계

- Frontend에서 시작된 요청의 Trace Context를 Backend 호출에 전달한다.
- 사용자에게 지원용 Trace 참조를 표시할 수 있다.
- Trace 참조는 업무 권한이나 Tenant 식별자를 대체하지 않는다.

---

## 12. 설정과 확장 지점

### 12.1 설정 범주

- 공통 요청 경계 기준 위치
- 기능 영역 노출 설정
- 스트리밍 사용 여부
- 상태 조회·갱신 간격
- 파일 업로드 Client 제한
- 페이지 크기와 표시 정책
- 세션 만료 UX
- 외부 모니터링 시스템 연결 방식
- 접근성·국제화 설정
- Client Telemetry와 마스킹 정책

### 12.2 구현 교체 경계

- Authentication Session Adapter
- Backend Client
- Streaming Transport
- Client State Store
- Citation Renderer
- Document Upload Client
- Evaluation Result Visualizer
- Frontend Telemetry

### 12.3 확장 지점

- 사용자 집단별 Frontend 분리
- 다국어 UI
- 문서 미리보기
- 선택적 자원 구성 비교 결과 시각화
- 외부 모니터링 Deep Link
- 실시간 업무 상태 갱신
- 승인 Workflow 화면

확장 기능도 Backend 책임과 외부 인증 경계를 변경하지 않는다.

---

## 13. 제약과 미결정 사항

### 13.1 확정된 제약

- 초기에는 하나의 Frontend 애플리케이션을 사용한다.
- Frontend는 각 Backend의 책임별 인터페이스를 통해 상호작용한다.
- 인증·조직 관리는 외부 책임이다.
- Tenant 격리의 최종 강제는 Backend가 수행한다.
- 일반 사용자는 동일 Tenant의 Knowledge Base를 공통으로 사용하고 자신의 대화 이력만 조회한다.
- Resource Management 화면의 접근 통제는 외부 운영 및 인증 체계가 담당한다.
- Citation과 제한 응답을 명확히 표시한다.
- Operations 화면은 외부 모니터링 시스템을 대체하지 않는다.

### 13.2 초기 구현 제외 범위

- 독립 Admin 인증 체계
- Micro-frontend
- 외부 모니터링 데이터 자체 저장·분석
- 외부 모델·검색 저장소의 배포 및 운영
- 평가 결과의 자동 운영 반영

### 13.3 미결정 사항

- UI Framework와 디자인 시스템
- Streaming 전송 방식
- 대용량 파일 Upload 방식과 제한
- 상태 Polling·Push 적용 범위
- Citation 원문 보기·다운로드 명세
- Dataset 편집과 검수 UX
- Operations 화면의 초기 업무 범위
- Client Cache·Offline·Draft 보존 정책
- 접근성 준수 목표와 국제화 초기 범위

---

## 14. 상위 설계 추적

| 상위 설계 책임 | 상세 설계 반영 |
|---|---|
| Frontend Chat | Chat Experience와 Answer·Citation View |
| Knowledge Management | Knowledge Experience와 Upload·처리 상태 |
| 지식 생성 전략 선택 | Strategy Selection Experience와 후보 비교·선택·최종 확인 |
| Resource Management | Resource Management Experience와 시스템 공통 구성 관리 |
| Quality Evaluation | Quality Experience와 Feedback·Run·Comparison |
| Operations | 업무 상태 화면과 외부 모니터링 책임 분리 |
| 외부 인증 경계 | Session Context와 자체 인증 미구현 |
| Tenant 중심 격리 | Tenant 변경 시 Client 데이터 격리와 Backend 재검증 |
| Backend Interface | 책임별 Backend 상호작용 접점 |
| Operations & Observability | Frontend Trace 연계와 민감정보 제외 |

---

## 15. 구현 수용 시나리오

| ID | 시나리오 | 기대 결과 |
|---|---|---|
| FRT-001 | 인증된 사용자 진입 | 외부에서 검증된 Tenant와 사용자 참조에 맞는 초기 화면 |
| FRT-002 | Tenant 전환 | 이전 Tenant 데이터·Draft 제거 후 새 데이터 조회 |
| FRT-003 | 질문 제출과 스트리밍 | 중복 Message 없이 진행·완료 상태 표시 |
| FRT-004 | 근거 부족 Answer | 제한 응답으로 명확히 표시 |
| FRT-005 | Citation 선택 | Answer에 연결된 허용 원본 위치 표시 |
| FRT-006 | 스트리밍 중단 | Query 상태 조회와 안전한 복구 |
| FRT-007 | 문서 등록 | 수용 상태와 후속 처리 상태 분리 표시 |
| FRT-008 | 문서 처리 실패 | 실패 요약과 허용된 재처리 Action 표시 |
| FRT-009 | 평가 부분 완료 | 성공 지표와 실패 Case를 함께 표시 |
| FRT-010 | 네트워크 재시도 | 동일 요청의 중복 업무 생성 방지 |
| FRT-011 | Tenant 또는 대화 소유권 불일치 | Backend 요청 또는 결과에 따라 안전하게 차단 |
| FRT-012 | Telemetry 검사 | 질문·문서·Answer·Token 원문 미포함 |

### 15.1 구현 완료 판정

- 각 화면의 정상·빈 결과·진행·부분 성공·오류 상태가 검증되어야 한다.
- Tenant 전환과 세션 만료에서 데이터가 섞이지 않아야 한다.
- 중복 제출과 네트워크 복구가 Backend 멱등성 명세와 일치해야 한다.
- 키보드와 보조기술로 핵심 흐름을 수행할 수 있어야 한다.

---

## 16. 상세 설계 완료 점검

- [x] 정의된 화면 영역과 Backend 책임 매핑을 완료했다.
- [x] Client 내부 모듈과 상태 생명주기를 정의했다.
- [x] 채팅·문서·평가·운영 흐름을 정의했다.
- [x] 스트리밍·장시간 처리·부분 성공 복구를 정의했다.
- [x] 외부 인증·Tenant·민감정보 경계를 정의했다.
- [x] 접근성과 Frontend 관찰성 기준을 정의했다.
- [x] API·Framework·배포 결정을 후속 설계로 분리했다.
- [x] 미결정 사항과 구현 수용 시나리오를 기록했다.
