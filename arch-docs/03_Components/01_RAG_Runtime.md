# Enterprise RAG `RAG Runtime` 상세 설계

## 1. 목적과 범위

RAG Runtime은 사용자 질문에 관련된 지식을 검색하고, 확인된 근거 범위 안에서 대화형 답변과 Citation을 제공하는 실시간 Backend 컴포넌트이다.

본 문서는 다음을 상세화한다.

- 대화, 검색, 근거 구성과 답변 생성 책임의 내부 분리
- 운영 요청과 평가 요청의 실행 경계
- 검색 결과의 유효성·충분성 판단과 제한 응답
- 질문부터 Citation까지의 추적 관계
- 외부 임베딩·검색 저장소·프롬프트·생성 자원 인터페이스
- 실시간 경로의 오류, 일관성, 보안과 관찰성

API 경로, DB Schema, 구체적인 검색·Reranking·Grounding 알고리즘과 배포 기술은 정의하지 않는다.

### 1.1 초기 구현 기준

- 운영 질의와 평가 질의를 동일한 검색·답변 핵심 흐름으로 처리한다.
- 평가 질의에는 별도의 Evaluation Context를 적용한다.
- 실시간 질의 경로에서 Knowledge Processing을 호출하지 않는다.
- 실시간 질의 경로에서 Knowledge Strategy Selection을 호출하지 않고 활성 Publication에 연결된 선택 전략 참조를 사용한다.
- 하나의 질문 실행은 하나의 Tenant와 명시적인 Knowledge Scope에 속한다.
- 검색 근거가 부족하면 외부 생성 모델의 일반 지식으로 보완하지 않는다.
- 응답 스트리밍 여부와 관계없이 최종 답변과 Citation의 일관된 완료 결과를 남긴다.

---

## 2. 책임과 경계

### 2.1 핵심 책임

- 대화와 메시지 관계 관리
- 질문 실행 컨텍스트 구성
- Knowledge Scope 강제
- 질문의 검색 표현 생성
- 게시된 지식 검색
- 검색 결과 검증·정리와 충분성 판단
- 답변 근거와 Citation 후보 구성
- 외부 프롬프트 적용과 생성 자원 호출
- 근거 기반 답변 또는 제한 응답 구성
- 질문, 검색 결과, 답변과 Citation 추적
- 운영 및 평가 실행 구분

### 2.2 입력과 출력

| 구분 | 주요 정보 |
|---|---|
| 입력 | Tenant Context, Subject Context, Request Context, Conversation 참조, 사용자 질문, Knowledge Scope, Trace Context, 선택적 Evaluation Context |
| 출력 | 질문 실행 결과, 검색 결과 요약, 답변, Citation, 제한 응답 사유, 실행 상태, 적용된 외부 자원 구성정보 |

사용자 질문과 답변 원문을 관찰정보에 기록하지 않으며, 업무 저장 여부와 보존 정책은 데이터 설계에서 결정한다.

### 2.3 소유하는 판단과 상태

RAG Runtime은 다음을 소유한다.

- Conversation과 Message의 업무 상태
- Query Execution의 상태
- 해당 질문에 적용할 Knowledge Scope의 유효성 판단
- 검색 결과의 범위·유효성·관련성·충분성 판단 결과
- Evidence Set의 구성
- 답변 생성 가능 여부
- 제한 응답 여부와 사유
- Answer와 Citation의 완료 상태

### 2.4 의존하는 책임

- 외부 인증 및 조직 시스템: 검증된 Tenant·Subject Context
- Resource Manager: 시스템 공통 외부 자원 구성과 호환성 정보
- Knowledge Processing: 게시된 지식과 검색 가능 상태의 의미
- 외부 임베딩 자원: 질문의 검색 표현
- 외부 검색 저장소: 지정 범위의 관련 지식
- 외부 프롬프트 시스템: 지정된 프롬프트
- 외부 생성 자원: 근거 기반 답변 후보
- 외부 모니터링 시스템: 제공된 OpenTelemetry 정보의 저장·분석·경보

### 2.5 수행하지 않는 역할

- 원본 문서와 Knowledge Base 생명주기 관리
- 문서 분석, 지식 구성과 게시
- 모델·검색 저장소·프롬프트 선택 및 운영
- 프롬프트 작성과 승인
- 평가 기준·피드백과 평가 결과 소유
- 사용자 인증과 조직 권한 원천 관리
- 근거 없는 일반 지식 답변

---

## 3. 내부 구성

### 3.1 내부 모듈

| 내부 모듈 | 주된 책임 |
|---|---|
| Request Context Control | 요청 컨텍스트 검증, Tenant와 Knowledge Scope 고정 |
| Conversation Management | Conversation과 Message 관계 및 운영·평가 실행 구분 |
| Query Preparation | 대화 맥락을 반영한 검색 목적과 질문 표현 입력 구성 |
| Retrieval Execution | 임베딩 자원과 검색 저장소를 사용한 관련 지식 탐색 |
| Result Qualification | 검색 결과 범위·유효성·관련성·중복·충분성 판단 |
| Evidence Management | 답변 근거, 원본 위치와 Citation 후보 구성 |
| Response Generation | 프롬프트 적용, 생성 자원 호출과 답변 후보 수용 |
| Grounding Assurance | 생성 결과와 Evidence의 연결 확인 및 제한 응답 결정 |
| Result Management | 질문·검색·답변·Citation 상태와 추적 관계 유지 |
| External Resource Interface | 임베딩·검색·프롬프트·생성 자원의 차이 격리 |
| Runtime Observability | 실행·외부 호출·오류 관찰정보 제공 |

### 3.2 내부 의존 방향

```text
Request Context Control
        ↓
Conversation Management
        ↓
Query Preparation
        ↓
Retrieval Execution
        ↓
Result Qualification
        ↓
Evidence Management
        ↓
Response Generation
        ↓
Grounding Assurance
        ↓
Result Management

Retrieval Execution · Response Generation
        ↓
External Resource Interface

모든 모듈
        ↓
Runtime Observability
```

응답 결과가 앞 단계로 돌아가더라도 정적 책임 의존 방향이 역전되는 것은 아니다.

### 3.3 상태 변경 책임

| 상태 | 변경 책임 |
|---|---|
| Conversation | Conversation Management |
| User Message | Conversation Management |
| Query Execution | Result Management |
| Retrieval Result | Result Qualification |
| Evidence Set | Evidence Management |
| Answer | Grounding Assurance와 Result Management |
| Citation | Evidence Management와 Result Management |

외부 자원 인터페이스는 업무 상태를 직접 결정하지 않고 호출 결과만 반환한다.

### 3.4 내부 Operation 명세

| Operation | 제공 모듈 | 목적 |
|---|---|---|
| ValidateRuntimeContext | Request Context Control | Tenant, Scope, 적용된 외부 자원 구성정보와 실행 목적 검증 |
| LoadConversationContext | Conversation Management | 현재 질문에 필요한 대화 맥락 제공 |
| PrepareRetrievalQuery | Query Preparation | 검색 목적과 질문 표현 입력 구성 |
| RetrieveKnowledge | Retrieval Execution | 지정 범위에서 관련 지식 탐색 |
| QualifyRetrievalResult | Result Qualification | 답변 근거로 사용할 결과와 충분성 판단 |
| AssembleEvidence | Evidence Management | 근거와 Citation 후보 구성 |
| GenerateGroundedAnswer | Response Generation | 프롬프트와 근거로 답변 후보 생성 |
| AssureGrounding | Grounding Assurance | 근거 범위 준수와 제한 응답 판단 |
| CompleteQueryExecution | Result Management | 최종 상태와 추적 관계 확정 |

---

## 4. 핵심 정보 모델

### 4.1 정보 정의

| 정보 | 의미 |
|---|---|
| Conversation | 하나의 Tenant 안에서 이어지는 질의응답 맥락 |
| Message | 사용자 질문 또는 시스템 답변 |
| Query Execution | 한 질문의 검색·답변 실행 단위 |
| Retrieval Query | 검색 목적에 맞게 구성된 질문 표현의 논리 정보 |
| Retrieval Result | 검색 저장소가 반환한 관련 지식 후보와 점수 |
| Qualified Result | 범위·유효성·관련성 검증을 통과한 검색 결과 |
| Evidence Set | 답변 생성에 허용된 지식 근거 집합 |
| Answer | 근거 범위 안에서 구성된 최종 응답 |
| Citation | Answer와 원본 문서·Knowledge Unit 위치의 관계 |
| 실행 외부 자원 구성정보 | 실행 당시 적용된 시스템 공통 외부 자원 구성과 정책 참조 |
| Evaluation Context | 평가 실행을 운영 요청과 구분하는 정보 |

### 4.2 정보 관계

```text
Conversation
  └─ Message
      └─ Query Execution
          ├─ Retrieval Query
          ├─ Retrieval Result
          │   └─ Qualified Result
          ├─ Evidence Set
          ├─ Answer
          │   └─ Citation
          └─ 실행 외부 자원 구성정보
```

평가 실행인 경우 Query Execution이 Evaluation Context를 추가로 참조한다.

### 4.3 불변 규칙

- 모든 정보는 하나의 Tenant에만 속한다.
- Conversation의 Tenant와 Query Execution의 Tenant는 같아야 한다.
- Conversation과 그 Message, Answer 및 Citation은 Tenant와 대화 소유 Subject가 모두 일치하는 경우에만 조회할 수 있다.
- Retrieval Result는 요청된 Knowledge Scope를 벗어날 수 없다.
- Evidence Set에는 Qualified Result만 포함할 수 있다.
- Citation은 현재 Evidence Set의 원본 위치만 참조할 수 있다.
- Answer가 `GROUNDED`이면 하나 이상의 근거 관계가 있어야 한다.
- 근거가 부족한 실행은 `LIMITED` 답변으로 완료하고 생성 모델 일반 지식으로 보완하지 않는다.
- Evaluation Context가 있는 실행은 운영 Conversation과 사용자 통계에 포함하지 않는다.
- 외부 자원 구성정보에는 Secret 원문을 포함하지 않는다.

### 4.4 구현용 논리 필드

후속 데이터·API 설계에서 최소한 다음 의미를 표현해야 한다.

| 정보 | 필수 의미 |
|---|---|
| Conversation | 식별자, Tenant, Subject 참조, 상태, 생성·갱신 시점 |
| Message | 식별자, Conversation 참조, 역할, 내용 참조, 순서, 생성 시점 |
| Query Execution | 식별자, Request 참조, Tenant, Scope, 실행 유형, 상태, 시작·종료 시점 |
| Retrieval Result | 실행 참조, Knowledge Unit 참조, 원본 위치, 관련도 정보, 순위, 유효성 |
| Evidence Set | 실행 참조, 선택된 결과 참조, 충분성 판단과 사유 |
| Answer | 실행 참조, 상태, 내용 참조, 제한 응답 사유, 완료 시점 |
| Citation | Answer 참조, Knowledge Unit·Document 참조, 원본 위치 |
| 외부 자원 구성정보 | 구성 식별 참조, 역할별 자원 참조, 호환성 참조와 적용 관계 |

실제 필드명, 내용 저장 방식과 보존 기간은 후속 설계에서 정의한다.

---

## 5. 상태와 생명주기

### 5.1 Conversation 상태

```text
ACTIVE
  → CLOSED
```

- `ACTIVE`: 새 질문을 수용할 수 있다.
- `CLOSED`: 새 질문을 수용하지 않으며 기존 이력만 조회할 수 있다.

Conversation 재개 정책은 후속 요구사항으로 남긴다.

### 5.2 Query Execution 상태

```text
ACCEPTED
  → RETRIEVING
  → QUALIFYING
  ├─ GENERATING
  │    → VALIDATING
  │    → COMPLETED
  ├─ LIMITED
  │    → COMPLETED
  └─ FAILED
```

| 상태 | 의미 |
|---|---|
| ACCEPTED | 컨텍스트 검증을 통과하고 실행이 생성됨 |
| RETRIEVING | 질문 표현 생성과 지식 검색 수행 중 |
| QUALIFYING | 검색 결과 검증과 충분성 판단 중 |
| GENERATING | 근거 기반 답변 후보 생성 중 |
| VALIDATING | 생성 결과의 근거 연결 확인 중 |
| LIMITED | 근거 부족 등으로 제한 응답 확정 |
| COMPLETED | 답변과 Citation 또는 제한 응답 완료 |
| FAILED | 재시도 또는 사용자 대응이 필요한 실패 |

### 5.3 Answer 상태

| 상태 | 의미 |
|---|---|
| GROUNDED | 확인된 근거와 Citation이 있는 답변 |
| LIMITED | 지식 범위 안에서 답할 수 없음을 알리는 응답 |
| REJECTED | 근거 위반 또는 결과 검증 실패로 사용자 답변으로 채택하지 않음 |

### 5.4 금지되는 상태 전이

- `FAILED → COMPLETED` 직접 전이
- `COMPLETED → GENERATING` 전이
- `LIMITED → GENERATING` 자동 전이
- 다른 Tenant의 Conversation으로 Query Execution 이동
- 완료된 Evidence Set의 근거를 유지하지 않은 Answer 교체

재실행은 기존 실행 상태를 되돌리지 않고 새로운 attempt 또는 Query Execution 관계로 표현한다.

### 5.5 상태 전이 구현 규칙

- 상태 변경 전 현재 상태와 Tenant를 확인한다.
- 완료 상태는 Answer와 Citation 또는 제한 응답 정보가 함께 확정된 뒤 기록한다.
- 외부 호출 성공만으로 업무 완료 상태를 기록하지 않는다.
- 상태 변경 실패를 외부 호출 재실행으로 바로 연결하지 않는다.
- 상태 전이와 결과 관계는 감사 가능한 실행정보를 남긴다.

---

## 6. 주요 처리 흐름

### 6.1 운영 질문 처리

```text
SubmitQuestion
  → 실행 컨텍스트 검증
  → Conversation 맥락 확인
  → 검색용 질문 준비
  → 질문 임베딩 생성
  → Tenant·Knowledge Scope 기반 검색
  → 결과 검증과 충분성 판단
  ├─ 충분함
  │   → Evidence 구성
  │   → 외부 프롬프트 적용
  │   → 답변 후보 생성
  │   → Grounding 확인
  │   → Answer·Citation 완료
  └─ 부족함
      → 제한 응답 완료
```

### 6.2 대화 맥락 반영

- 현재 질문 해석에 필요한 이전 Message만 사용한다.
- 대화 이력으로 검색 범위나 Tenant를 확장하지 않는다.
- 이전 답변의 내용은 현재 지식 근거로 간주하지 않는다.
- 독립 질문 재구성이 필요한 경우 적용된 외부 자원 구성정보의 외부 자원만 사용한다.
- 재구성 전·후 질문의 관계를 추적한다.

### 6.3 평가 질문 처리

```text
ExecuteEvaluationQuery
  → Evaluation Context 검증
  → 운영 Conversation과 분리된 실행 생성
  → 운영과 동일한 검색·답변 핵심 흐름
  → 평가용 실행 결과 반환
  → 운영 대화·사용자 통계 미반영
```

### 6.4 지식 생성 전략 비교 질문 처리

```text
ExecuteStrategyComparison
  → Strategy Selection Context와 후보 임시 범위 검증
  → 운영 Conversation·평가 실행과 분리된 실행 생성
  → 지정 후보의 검색·답변·Citation 결과 생성
  → 후보 결과 참조 반환
  → 운영 대화·사용자 통계 미반영
```

서로 다른 후보, 운영 지식 또는 호환되지 않는 임베딩 범위를 하나의 실행에 혼합하지 않는다.

### 6.5 근거 부족 처리

다음 조건에서는 생성 자원 호출을 생략하거나 결과를 채택하지 않고 제한 응답을 제공할 수 있다.

- 검색 결과 없음
- 검색 결과가 Tenant 또는 Scope 검증 실패
- 최소한의 관련성·충분성 기준 미충족
- 근거 간 충돌로 신뢰 가능한 답변 구성 불가
- 생성 결과가 Evidence와 연결되지 않음

판단 알고리즘과 임계값은 설정 및 검색 상세 정책으로 분리한다.

### 6.6 스트리밍 응답

- 스트리밍은 전달 방식이며 Answer의 최종 업무 상태와 구분한다.
- 스트리밍 중간 조각은 완료 Answer로 간주하지 않는다.
- 실패 시 이미 전달된 부분과 최종 실패 상태의 관계를 식별할 수 있어야 한다.
- Citation은 근거가 확정된 범위만 제공한다.
- 구체적인 전송 명세는 API 설계에서 정의한다.

### 6.7 재실행

- 재실행 요청은 원 실행과 원인을 참조한다.
- 원 실행에 적용된 외부 자원 구성정보를 재사용할지 현재 적용 가능한 공통 구성정보를 사용할지 명시한다.
- 원 실행의 Answer와 Citation을 덮어쓰지 않는다.
- 운영 요청과 평가 요청의 실행 유형을 변경하지 않는다.

---

## 7. 컴포넌트 Operation 명세

### 7.1 제공 Operation

| Operation | 목적 | 상태 변경 |
|---|---|---|
| CreateConversation | 새 대화 맥락 생성 | Conversation 생성 |
| GetConversation | Tenant 및 대화 소유자 범위 안의 대화와 메시지 조회 | 없음 |
| CloseConversation | 대화의 추가 질문 수용 종료 | Conversation 변경 |
| SubmitQuestion | 운영 질문 검색·답변 실행 | Message와 Query Execution 생성·변경 |
| ExecuteEvaluationQuery | 평가 컨텍스트의 검색·답변 실행 | 평가용 Query Execution 생성·변경 |
| ExecuteStrategyComparison | 지정 후보 임시 범위의 검색·답변 실행 | 전략 비교용 Query Execution 생성·변경 |
| GetQueryResult | 실행 상태, 답변과 Citation 조회 | 없음 |

### 7.2 SubmitQuestion

- 필수 입력: Tenant, Subject, Request, Conversation, 질문, Knowledge Scope, Trace Context
- 성공 결과: Query Execution 참조, Answer 또는 진행 상태, Citation
- 거부 조건: Tenant 누락·불일치, 대화 소유자 불일치, 닫힌 Conversation, 허용되지 않은 Scope, 적용 가능한 공통 자원 구성 부재
- 멱등성: 같은 Tenant와 멱등성 범위의 동일 요청은 같은 실행을 반환해야 한다.

### 7.3 ExecuteEvaluationQuery

- 필수 입력: Tenant, Request, Evaluation Context, 질문, Knowledge Scope, Trace Context
- 성공 결과: 평가에 필요한 검색 결과, Evidence, Answer와 Citation 참조
- 거부 조건: 평가 실행 식별정보 누락, 운영 Conversation 지정, Tenant·평가 대상 범위 불일치
- 멱등성: 평가 Case와 실행 attempt의 의미에 따라 중복 실행을 구분한다.

### 7.4 ExecuteStrategyComparison

- 필수 입력: Tenant, Request, Strategy Selection Context, 후보 임시 범위, 질문, 적용된 외부 자원 구성정보, Trace Context
- 성공 결과: 후보별 검색 결과, Evidence, Answer, Citation과 처리 결과 참조
- 거부 조건: 선택 과정·후보 식별정보 누락, 운영 지식 또는 다른 후보 혼합, Tenant·Knowledge Base 불일치
- 멱등성: 같은 선택 과정·비교 질문·후보·attempt 범위에서 중복 실행을 구분한다.

### 7.5 외부에 요구하는 Operation

| 외부 역할 | 요구 Operation | 기대 결과 |
|---|---|---|
| 임베딩 자원 | CreateQueryRepresentation | 검색 저장소와 호환되는 질문 표현 |
| 검색 저장소 | SearchKnowledge | Tenant·Scope가 적용된 관련 지식 후보 |
| 프롬프트 시스템 | ResolvePrompt | 지정 참조에 해당하는 프롬프트와 명세정보 |
| 생성 자원 | GenerateAnswer | Evidence 범위 기반 답변 후보 |

구체적인 외부 명세는 별도 Interface/API 명세에서 정의한다.

---

## 8. 오류와 복구

### 8.1 오류 분류

| 분류 | 예시 | 기본 처리 |
|---|---|---|
| Context 오류 | Tenant·Scope·Evaluation Context 누락 또는 불일치 | 실행 전 거부 |
| 상태 충돌 | 닫힌 Conversation, 완료 실행 재변경 | 충돌 반환 |
| 외부 자원 일시 오류 | Timeout, 일시적 사용 불가 | 정책 범위 내 재시도 |
| 외부 자원 영구 오류 | 호환성 불일치, 적용할 수 없는 외부 자원 구성정보 | 실패 확정 및 운영 조치 |
| 검색 결과 부족 | 결과 없음, 충분성 미달 | 제한 응답 |
| Grounding 오류 | 생성 결과가 Evidence와 불일치 | 결과 거부 또는 제한 응답 |
| 내부 일관성 오류 | Answer-Citation 관계 누락 | 완료 금지 및 실패 |

### 8.2 복구 원칙

- 재시도 가능한 외부 오류와 업무상 제한 응답을 구분한다.
- 생성 호출만 재시도할 때 동일 Evidence와 외부 자원 구성정보를 유지한다.
- 검색부터 재실행하면 새로운 attempt로 구분한다.
- 외부 호출 성공 여부와 로컬 완료 여부를 각각 추적한다.
- 실패한 실행을 감추기 위해 빈 Answer를 성공으로 반환하지 않는다.

### 8.3 부분 성공

- 검색 성공·생성 실패: 검색 결과를 유지하고 생성 재시도 가능 상태로 기록한다.
- 생성 성공·결과 저장 실패: 외부 생성 호출 식별정보를 유지하고 중복 생성 여부를 판단한다.
- Answer 완료·Citation 구성 실패: 사용자 완료 응답으로 확정하지 않는다.
- 스트리밍 일부 전달·최종 실패: 전달 상태와 실패 상태를 함께 식별한다.

---

## 9. 동시성, 멱등성과 일관성

### 9.1 동시성

- 하나의 Conversation에 복수 질문을 허용할지는 순서 정책으로 명시한다.
- 이전 질문 의존성이 있는 요청은 Message 순서를 기준으로 맥락을 구성한다.
- 동시에 완료된 Answer가 Conversation 순서를 역전시키지 않도록 한다.
- 평가 실행은 운영 Conversation Lock이나 순서에 참여하지 않는다.

### 9.2 멱등성

- CreateConversation과 SubmitQuestion은 Tenant가 포함된 멱등성 범위를 가진다.
- 동일 키에 다른 질문이나 Scope가 들어오면 충돌로 처리한다.
- 외부 생성·임베딩 호출 재시도에는 원 호출과 attempt 관계를 유지한다.
- 조회 Operation은 상태를 변경하지 않는다.

### 9.3 업무 일관성 경계

Query Execution의 완료 일관성 경계는 다음을 포함한다.

- 질문과 실행 관계
- 최종 Evidence Set
- Answer 상태와 내용 참조
- Citation 관계
- 적용된 외부 자원 구성정보

외부 검색 저장소와 모델 제공 시스템은 이 로컬 일관성 경계에 포함되지 않는다.

### 9.4 최신성

- 검색에는 게시 완료된 지식만 사용한다.
- 검색에는 실행에 적용된 외부 자원 구성정보와 호환되며 활성화된 지식 게시 단위만 사용한다.
- 하나의 검색 범위에 서로 호환되지 않는 임베딩 구성이 적용된 게시 단위가 포함되면 검색을 수행하지 않는다.
- 문서 게시 직후 검색 가시성 시점은 Knowledge Processing과 검색 저장소 명세에 따른다.
- 질의 중 게시 상태가 변경되더라도 실행 당시 Retrieval Result와 외부 자원 구성정보를 유지한다.

---

## 10. Tenant, 보안과 권한

### 10.1 신뢰 경계

- 외부 요청 경계가 인증한 Context를 수용하되 Backend에서 필수 Context와 대상 관계를 다시 확인한다.
- 사용자 Token의 원천 권한을 RAG Runtime이 새로 계산하지 않는다.
- 컴포넌트 간 요청은 원 Tenant와 Trace Context를 보존해야 한다.

### 10.2 Tenant 격리

- Conversation, Message, Query Execution과 모든 검색 조건에 Tenant를 적용한다.
- 동일 Tenant 안에서도 Conversation, Message, Answer와 Citation 조회에는 대화 소유 Subject를 함께 적용한다.
- Subject는 대화 소유권과 감사에만 사용하며 Knowledge Base나 문서에 대한 사용자별 권한으로 사용하지 않는다.
- 사용자가 검색 필터로 Tenant 조건을 제거하거나 변경할 수 없다.
- 검색 저장소 응답도 Tenant와 Scope를 재검증한다.
- Citation이 다른 Tenant의 문서나 Knowledge Unit을 참조하지 않도록 한다.

### 10.3 민감정보

- 인증정보와 Secret을 Prompt, Answer, 실행 이력과 로그에 포함하지 않는다.
- 질문, 검색 원문과 답변은 업무 데이터로 취급하며 접근·보존 정책을 적용한다.
- 외부 생성 자원에는 허용된 Evidence와 필요한 대화 맥락만 전달한다.
- 오류 메시지에 외부 Endpoint, 인증정보와 원문 Prompt를 노출하지 않는다.

---

## 11. 관찰성과 운영정보

### 11.1 Trace

주요 Span 범주는 다음 의미를 표현할 수 있어야 한다.

- 질문 실행 전체
- 대화 맥락 구성
- 질문 표현 생성
- 지식 검색
- 결과 검증과 Evidence 구성
- 프롬프트 조회
- 답변 생성
- Grounding 확인
- 결과 저장

Span 이름과 속성은 OpenTelemetry 상세 설계에서 확정한다.

### 11.2 Metric

- 질문 실행 수와 성공·실패·제한 응답 비율
- 검색 결과 없음과 충분성 미달 비율
- 검색·생성·전체 응답 지연
- 외부 자원 역할별 호출 성공률과 지연
- Grounding 결과 거부 비율
- 평가 실행과 운영 실행 비율
- 스트리밍 중단 비율

Tenant 식별자를 고카디널리티 Metric Label로 직접 사용하지 않는다.

### 11.3 구조화 Log

- Query Execution 수용과 완료
- 상태 전이와 거부 사유
- 외부 호출 attempt와 결과 분류
- 제한 응답 사유
- Grounding 위반
- 일관성·멱등성 충돌

질문·답변·Evidence 원문은 기본 로그에서 제외한다.

### 11.4 운영 상태

컴포넌트 자체 실행 가능 여부와 필수 외부 자원 사용 가능 여부를 구분해 표현해야 한다.

구체적인 Health·Readiness Endpoint는 API 및 물리 설계에서 정의한다.

---

## 12. 설정과 확장 지점

### 12.1 설정 범주

- 대화 맥락 사용 범위
- 검색 결과 수와 충분성 판단 정책 참조
- 결과 정리와 Reranking 정책 참조
- Prompt Reference
- 생성 응답 제약
- Timeout과 역할별 재시도 정책
- 스트리밍 허용 여부
- 운영·평가 결과 보존 정책 참조
- 관찰정보와 마스킹 정책

설정값 자체와 Tenant·Knowledge Base 적용 우선순위는 후속 설정 설계에서 정의한다.

### 12.2 구현 교체 경계

- Query Rewriter
- Embedding Client
- Search Store Client
- Result Ranker
- Prompt Resolver
- Generation Client
- Grounding Validator
- Conversation Repository
- Runtime Result Repository

이 명칭은 책임 경계이며 구체 클래스나 독립 서비스 이름을 확정하지 않는다.

### 12.3 확장 지점

- 키워드·벡터·복합 검색 전략
- Reranker
- 다중 Knowledge Base 검색
- 답변 후검증 수단
- 다국어 질문 처리
- Citation 세분화
- 검색·답변 정책 실험

확장 기능도 Tenant와 Evidence 불변 규칙을 우회할 수 없다.

---

## 13. 제약과 미결정 사항

### 13.1 확정된 제약

- 실시간 질의 경로에서 Knowledge Processing을 호출하지 않는다.
- Resource Manager에서 관리되고 실행에 적용된 외부 자원 구성정보의 자원만 사용한다.
- Tenant와 Knowledge Scope를 모든 검색에 강제한다.
- 근거가 부족하면 제한 응답을 제공한다.
- 평가 실행은 운영 대화와 분리한다.
- 전략 비교 실행은 운영 대화·평가 실행과 분리하고 지정된 후보 임시 범위만 사용한다.
- 관찰정보는 OpenTelemetry 기반으로 외부 시스템에 제공한다.

### 13.2 초기 구현 제외 범위

- 웹 검색과 외부 지식 자동 보완
- Agent 기반 자율 업무 수행
- 모델 자동 선택과 라우팅
- 사용자 인증·조직 관리
- 평가 결과 기반 자동 운영 변경

### 13.3 미결정 사항

- 대화 동시 질문 허용 및 순서 정책
- 대화 맥락 최대 범위와 요약 정책
- 검색 결과 충분성·Grounding 판단 방식
- 스트리밍 중 Citation 제공 시점
- 게시된 Knowledge Base 참조정보의 제공·최신성 방식
- Runtime 업무정보의 저장·보존·삭제 정책
- 외부 자원 실패별 재시도 기본값
- 답변 후검증의 초기 포함 여부

---

## 14. 상위 설계 추적

| 상위 설계 책임 | 상세 설계 반영 |
|---|---|
| Retrieval | Query Preparation, Retrieval Execution, Result Qualification, Evidence Management |
| Conversation & Response | Conversation Management, Response Generation, Grounding Assurance, Result Management |
| Tenant 중심 격리 | Request Context Control과 모든 정보·검색 불변 규칙 |
| 지식 범위 제한 | Evidence Set과 제한 응답 |
| 추적 가능한 결과 | Query Execution부터 Answer·Citation까지의 관계 |
| External Resource Interface | 임베딩·검색·프롬프트·생성 접점 |
| Operations & Observability | Runtime Observability와 OTel 관찰정보 |
| Quality Evaluation 의존 | ExecuteEvaluationQuery와 Evaluation Context |
| 지식 생성 전략 선택 의존 | ExecuteStrategyComparison과 Strategy Selection Context |

---

## 15. 구현 수용 시나리오

| ID | 시나리오 | 기대 결과 |
|---|---|---|
| RRT-001 | 유효한 Tenant와 Scope로 질문 | 해당 범위의 근거 기반 Answer와 Citation 완료 |
| RRT-002 | 검색 결과 없음 | 생성 모델 일반 지식 호출 없이 제한 응답 |
| RRT-003 | 다른 Tenant 검색 결과 반환 | 결과 제외, 격리 위반 기록과 안전한 실패 |
| RRT-004 | 동일 멱등성 요청 반복 | 같은 Query Execution 결과 반환 |
| RRT-005 | 동일 키에 다른 질문 | 충돌 처리 |
| RRT-006 | 생성 자원 일시 실패 | 정책 범위 재시도 후 상태 보존 |
| RRT-007 | Answer가 Evidence와 불일치 | 결과 거부 또는 제한 응답 |
| RRT-008 | 평가 질문 실행 | 운영 Conversation·사용자 통계 미변경 |
| RRT-009 | 스트리밍 중 실패 | 부분 전달과 최종 실패 상태 추적 |
| RRT-010 | 완료 Answer의 Citation 조회 | 실행 당시 근거와 원본 위치 반환 |
| RRT-011 | 닫힌 Conversation에 질문 | 실행 생성 없이 거부 |
| RRT-012 | 게시되지 않은 지식 참조 | 검색 대상에서 제외 |

### 15.1 구현 완료 판정

- 수용 시나리오가 자동 또는 통합 테스트로 검증 가능해야 한다.
- 상태 전이와 멱등성 충돌이 명시적으로 확인되어야 한다.
- Tenant 교차 접근과 근거 없는 답변이 차단되어야 한다.
- 외부 호출과 전체 질문 실행이 하나의 Trace로 연결되어야 한다.

---

## 16. 상세 설계 완료 점검

- [x] 상위 책임과 컴포넌트 경계를 유지했다.
- [x] 내부 모듈의 책임과 의존 방향을 정의했다.
- [x] 핵심 정보, 상태와 불변 규칙을 정의했다.
- [x] 운영·평가 질문과 제한 응답 흐름을 정의했다.
- [x] 의미적 Operation과 오류·복구 원칙을 정의했다.
- [x] Tenant, 민감정보와 관찰성 제약을 정의했다.
- [x] API·DB·제품 결정을 후속 설계로 분리했다.
- [x] 미결정 사항과 구현 수용 시나리오를 기록했다.
