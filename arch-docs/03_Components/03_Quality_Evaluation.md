# Enterprise RAG `Quality Evaluation` 상세 설계

## 1. 목적과 범위

Quality Evaluation은 사용자 피드백과 반복 가능한 평가 기준을 관리하고, 운영 또는 평가 실행에서 생성된 검색 결과와 응답을 평가하여 품질 개선 판단의 근거를 제공하는 Backend 컴포넌트이다.

지식 생성 전략 선택에서 발생한 후보 선택은 운영 답변에 대한 Feedback이 아니며, 초기 전략 선택의 필수 실행 경로에는 Quality Evaluation이 참여하지 않는다.

본 문서는 다음을 상세화한다.

- 피드백과 평가 대상 결과의 연결
- 평가 기준·Dataset·Case와 실행 생명주기
- 평가 실행 컨텍스트를 통한 RAG Runtime 사용
- 외부 평가 수단과 RAGAS 같은 Framework의 교체 가능한 인터페이스
- 평가 결과 집계와 개선 후보 식별
- 선택적 확장인 적용 외부 자원 구성에 따른 평가 결과 비교
- 평가와 운영 설정 변경의 분리

평가 지표의 수학적 산식, RAGAS 버전, 평가 모델 선정, API·DB Schema와 배포 제품은 정의하지 않는다.

### 1.1 초기 구현 기준

- 사용자 피드백과 오프라인 평가는 서로 다른 근거로 보존한다.
- 평가 실행은 운영 질의응답과 분리된 Evaluation Context를 사용한다.
- 동일 평가 기준과 대상 조건으로 반복 실행할 수 있어야 한다.
- 평가 당시 Runtime·지식·외부 자원·정책 참조를 평가 실행 조건으로 확정하고 유지한다.
- 평가 결과는 운영 설정을 자동 변경하지 않는다.
- RAGAS는 선택 가능한 외부 평가 수단 중 하나로 취급한다.
- 서로 다른 외부 자원 구성의 비교 평가는 초기 핵심 범위가 아닌 선택적 확장으로 취급한다.

---

## 2. 책임과 경계

### 2.1 핵심 책임

- 사용자 피드백 수용과 대상 연결
- 평가 기준, Dataset과 Case 관리
- 평가 실행과 attempt 상태 관리
- RAG Runtime 평가 질의 조정
- 검색·Evidence·Answer·Citation 평가 대상 구성
- 규칙 기반 또는 외부 평가 수단 호출
- Case별 평가 결과 수용
- 실행 단위 지표 집계
- 품질 변화와 개선 필요 영역 식별
- 선택적 확장으로 적용 외부 자원 구성에 따른 평가 결과 비교

### 2.2 입력과 출력

| 구분 | 주요 정보 |
|---|---|
| 입력 | Tenant Context, Request Context, 피드백 대상 참조, 평가 기준·Dataset, 평가 대상 조건, Runtime 실행 결과, Trace Context |
| 출력 | Feedback 참조, Evaluation Run 상태, Case Result, Metric Result, 개선 후보와 실패 정보, 선택적 비교 결과 |

### 2.3 소유하는 판단과 상태

- Feedback의 유효성·분류와 대상 관계
- Evaluation Criteria·Dataset·Case의 상태
- Evaluation Run과 Case Execution의 상태
- 평가 대상과 실행 조건의 완전성
- 평가 결과의 수용·집계 가능 여부
- 품질 변화와 개선 후보 분류
- 선택적 비교 실행 시 대상 외부 자원 구성정보의 비교 가능 여부

### 2.4 의존하는 책임

- RAG Runtime: 평가 컨텍스트의 검색·답변 실행
- Knowledge Processing: 평가 대상 지식 범위와 문서 버전 참조
- Resource Manager: 시스템 공통 외부 평가 자원 구성
- 외부 평가 수단: 외부 지표 산출
- 업무 전문가 또는 외부 관리 주체: 검증된 평가 기준
- 외부 모니터링 시스템: 평가 실행 관찰정보 활용

### 2.5 수행하지 않는 역할

- 운영 검색·답변 정책 자동 변경
- 비교 대상 외부 자원 구성정보의 자동 승격과 배포
- 평가 모델·도구 자동 선택
- 운영 Conversation과 Answer 변경
- RAGAS 등 평가 도구 운영
- 문서 지식화와 사용자 답변 생성
- 사용자 인증과 조직 관리
- 최초 지식 생성 전 후보 전략 비교 과정과 사용자 선택 관리
- 후보 결과에 따른 지식 생성 전략 확정

---

## 3. 내부 구성

### 3.1 내부 모듈

| 내부 모듈 | 주된 책임 |
|---|---|
| Quality Request Control | Tenant, 요청 목적, 대상과 적용된 외부 자원 구성정보 검증 |
| Feedback Management | 피드백 수용, 분류와 평가 대상 연결 |
| Evaluation Criteria Management | 기준, Dataset, Case와 변경 관계 관리 |
| Evaluation Planning | 대상, 지표와 Case를 포함한 평가 실행 조건 구성 |
| Evaluation Execution | Run·attempt 조정과 Runtime 평가 질의 실행 |
| Evaluation Target Assembly | 질문·검색·Evidence·Answer·기준답변을 평가 입력으로 구성 |
| Evaluator Interface | 규칙 기반·외부 평가 수단의 차이 격리 |
| Result Aggregation | Case Result 검증, 지표 집계와 누락 처리 |
| Quality Comparison | 선택적 확장인 적용 외부 자원 구성에 따른 평가 결과 비교 |
| Quality Result Management | 상태, 결과, 평가 실행 조건과 추적 관계 관리 |
| Quality Observability | 평가 실행·외부 호출·오류 관찰정보 제공 |

### 3.2 내부 의존 방향

```text
Quality Request Control
        ├─→ Feedback Management
        └─→ Evaluation Criteria Management
                    ↓
            Evaluation Planning
                    ↓
            Evaluation Execution
                    ↓
        Evaluation Target Assembly
                    ↓
            Evaluator Interface
                    ↓
            Result Aggregation
              ├─────┴─────→ Quality Result Management
              └─ 선택적 → Quality Comparison
                              ↓
                    Quality Result Management

모든 모듈
        ↓
Quality Observability
```

### 3.3 상태 변경 책임

| 상태 | 변경 책임 |
|---|---|
| Feedback | Feedback Management |
| Evaluation Criteria·Dataset·Case | Evaluation Criteria Management |
| Evaluation Run·Case Execution | Evaluation Execution |
| Case Result·Metric Result | Result Aggregation |
| Comparison Result | 선택적 Quality Comparison |
| 평가 실행 조건·추적 관계 | Quality Result Management |

### 3.4 내부 Operation 명세

| Operation | 제공 모듈 | 목적 |
|---|---|---|
| ValidateQualityRequest | Quality Request Control | Tenant·대상·요청 목적 검증 |
| RecordFeedback | Feedback Management | 피드백과 대상 결과 연결 |
| DefineEvaluationDataset | Evaluation Criteria Management | 반복 평가 기준 구성 |
| PlanEvaluationRun | Evaluation Planning | 실행 대상·조건·지표 확정 |
| ExecuteEvaluationCases | Evaluation Execution | Runtime을 통한 Case 실행 |
| AssembleEvaluationTarget | Evaluation Target Assembly | 평가기 입력 구성 |
| EvaluateTarget | Evaluator Interface | 내부·외부 평가 수행 |
| AggregateEvaluationResults | Result Aggregation | Case 결과 검증과 집계 |
| CompareQualityResults | Quality Comparison | 선택적으로 적용 외부 자원 구성에 따른 평가 결과 비교 |
| CompleteEvaluationRun | Quality Result Management | 실행 결과와 추적 관계 완료 |

---

## 4. 핵심 정보 모델

### 4.1 정보 정의

| 정보 | 의미 |
|---|---|
| Feedback | 사용자가 검색 결과 또는 Answer에 제공한 평가 |
| Feedback Target | 피드백 대상 Query Execution·Answer·Citation·Retrieval Result 참조 |
| Evaluation Criteria | 품질을 판단하는 관점과 기대 조건 |
| Evaluation Dataset | 반복 평가에 사용하는 Case 집합 |
| Evaluation Case | 질문, 기대 결과·근거·출처와 적용 범위 |
| Evaluation Run | 특정 Dataset과 대상 조건을 평가하는 실행 단위 |
| Evaluation Attempt | 실패·재실행을 구분하는 Run 시도 |
| 평가 실행 조건 | 지식 버전, Runtime 조건과 적용된 외부 자원 구성정보 |
| Case Execution | 하나의 Case에 대한 Runtime 실행 |
| Case Result | 하나의 Case와 하나의 지표에 대한 결과 |
| Metric Result | Run 수준으로 집계된 품질 결과 |
| Comparison Result | 선택적 확장에서 비교한 외부 자원 구성정보 간 결과 차이와 해석 |
| Improvement Candidate | 검토가 필요한 품질 개선 영역 |

### 4.2 정보 관계

```text
Evaluation Dataset
  └─ Evaluation Case
      └─ Evaluation Run
          └─ Evaluation Attempt
              ├─ 평가 실행 조건
              ├─ Case Execution
              │   └─ Case Result
              ├─ Metric Result
              └─ Comparison Result

Feedback
  └─ Feedback Target
      └─ 운영 Query Execution 결과
```

### 4.3 불변 규칙

- 모든 Feedback·Dataset·Run·Result는 하나의 Tenant에 속한다.
- Feedback Target과 Feedback의 Tenant는 같아야 한다.
- Evaluation Case의 지식 범위는 Dataset과 Run의 허용 범위를 벗어날 수 없다.
- Run 시작 후 평가 실행 조건은 변경되지 않는다.
- Case Result는 실제 Case Execution 또는 명시적인 정적 평가 대상에 연결되어야 한다.
- 서로 다른 평가 지표 버전과 판단 기준의 결과는 동일 값처럼 직접 비교하지 않는다.
- 자동 생성된 평가 Case는 검수 상태 없이 기준 Dataset의 확정 Case가 될 수 없다.
- 선택적 Comparison Result는 대상 외부 자원 구성정보의 Dataset·지표 호환성을 확인해야 한다.
- 평가 결과가 운영 설정을 직접 변경하지 않는다.

### 4.4 구현용 논리 필드

| 정보 | 필수 의미 |
|---|---|
| Feedback | 식별자, Tenant, Subject 참조, Target, 유형·값·의견 참조, 생성 시점 |
| Dataset | 식별자, Tenant, 이름·목적, 버전, 상태, 생성·검수 정보 |
| Case | 식별자, Dataset, 질문, 기대 답변·근거·출처 참조, Scope, 상태 |
| Run | 식별자, Dataset version, 실행 목적, 대상 조건, 상태, 시작·종료 시점 |
| 평가 실행 조건 | 지식·Runtime·지표와 적용된 외부 자원 구성정보 |
| Case Execution | Run, Case, Runtime 실행 참조, 상태, 오류 |
| Case Result | Case Execution, Metric, 값·판정·근거, 평가 수단 참조 |
| Comparison | 비교 대상 외부 자원 구성정보의 Run, 지표별 차이, 호환성·판정 |

---

## 5. 상태와 생명주기

### 5.1 Evaluation Dataset 상태

```text
DRAFT
  → REVIEWED
  → ACTIVE
  → RETIRED
```

- `DRAFT`: 작성·자동 생성·편집 중
- `REVIEWED`: 업무 검토 완료
- `ACTIVE`: 평가 실행에 사용할 수 있음
- `RETIRED`: 신규 실행에 사용하지 않음

### 5.2 Evaluation Run 상태

```text
PLANNED
  → RUNNING
  → AGGREGATING
  ├─ COMPLETED
  ├─ PARTIALLY_COMPLETED
  ├─ FAILED
  └─ CANCELLED
```

| 상태 | 의미 |
|---|---|
| PLANNED | Dataset·대상·지표 등 평가 실행 조건 확정 |
| RUNNING | Case 실행과 평가 수행 중 |
| AGGREGATING | Case 결과 검증과 집계 중 |
| COMPLETED | 요구된 결과가 정상 집계됨 |
| PARTIALLY_COMPLETED | 일부 Case·지표 실패를 명시하고 결과 제공 |
| FAILED | 유효한 평가 결과를 제공할 수 없음 |
| CANCELLED | 실행 중단 요청이 반영됨 |

### 5.3 Case Execution 상태

```text
PENDING
  → EXECUTING
  → EVALUATING
  ├─ COMPLETED
  ├─ FAILED
  └─ SKIPPED
```

### 5.4 Feedback 상태

피드백은 원문을 덮어쓰기보다 생성·철회·검토 관계를 유지한다.

```text
RECORDED
  ├─ REVIEWED
  └─ WITHDRAWN
```

### 5.5 금지되는 상태 전이

- `DRAFT Dataset`으로 운영 또는 평가 Run 완료
- `COMPLETED Run → RUNNING`
- 평가 실행 조건을 변경한 후 같은 Run을 계속 실행
- 실패 Case 결과를 성공 지표에 포함
- 다른 Tenant Run 사이의 Comparison 생성

재평가는 새 attempt 또는 Run으로 표현한다.

---

## 6. 주요 처리 흐름

### 6.1 사용자 피드백

```text
SubmitFeedback
  → Tenant와 Feedback Target 검증
  → 피드백 유형·값 수용
  → 운영 결과와 관계 저장
  → 필요 시 품질 이슈 후보 분류
  → 처리 결과 반환
```

피드백은 검색·답변 설정을 즉시 변경하지 않는다.

### 6.2 평가 Dataset 구성

- 업무 전문가가 작성한 질문·기대 근거를 수용한다.
- 운영 질문 또는 부정 피드백을 Case 후보로 만들 수 있다.
- 자동 생성 후보는 `DRAFT`로 구분한다.
- 업무 검토 후 평가에 사용할 Dataset version을 활성화한다.
- Case 변경 시 기존 Run 재현을 위해 새 Dataset version을 사용한다.

### 6.3 평가 실행

```text
StartEvaluation
  → Dataset·대상 조건·지표 검증
  → 평가 실행 조건 확정
  → Case별 Evaluation Context 생성
  → RAG Runtime ExecuteEvaluationQuery
  → 검색·Evidence·Answer·Citation 결과 수용
  → 평가 입력 구성
  → 내부 규칙 또는 외부 평가 수단 실행
  → Case Result 검증
  → Metric Result 집계
  → Run 완료
```

### 6.4 선택적 확장: 자원 구성 비교 평가

```text
CompareEvaluationRuns
  → 외부 자원 구성정보·Dataset·지표 호환성 확인
  → 비교 대상 결과 정렬
  → 지표 변화·실패·비용·지연 정보 비교
  → 개선·저하·판단 불가 분류
  → Comparison Result와 검토 항목 제공
```

비교 평가는 시스템 공통으로 관리되는 외부 자원 구성정보만 대상으로 하며 Tenant별 자원 할당이나 운영 구성의 자동 변경으로 사용하지 않는다.

### 6.5 부분 평가

- Runtime 실패 Case와 Evaluator 실패 Case를 구분한다.
- 실패 결과를 점수 0으로 임의 변환하지 않는다.
- 집계에서 제외한 Case와 이유를 기록한다.
- 완료 기준에 미달하면 `PARTIALLY_COMPLETED` 또는 `FAILED`로 분류한다.

---

## 7. 컴포넌트 Operation 명세

### 7.1 제공 Operation

| Operation | 목적 | 상태 변경 |
|---|---|---|
| SubmitFeedback | 사용자 피드백 기록 | Feedback 생성 |
| CreateEvaluationDataset | 평가 Dataset 초안 생성 | Dataset 생성 |
| ReviewEvaluationDataset | Dataset 검수 상태 변경 | Dataset 변경 |
| StartEvaluation | 평가 Run 시작 | Run·Case Execution 생성 |
| GetEvaluationStatus | Run과 Case 진행 조회 | 없음 |
| GetEvaluationResult | Case·Metric 결과 조회 | 없음 |
| CompareEvaluationRuns | 선택적으로 적용 외부 자원 구성에 따른 평가 결과 비교 | Comparison 생성 |
| CancelEvaluation | 실행 중단 요청 | Run·Case 상태 변경 |

### 7.2 StartEvaluation

- 필수 입력: Tenant, Request, Dataset version, 평가 대상 조건, 지표·Evaluator 참조, Trace Context
- 성공 결과: Evaluation Run 참조와 평가 실행 조건 요약
- 거부 조건: 비활성 Dataset, Tenant·Scope 불일치, 지표·Evaluator 참조 누락
- 멱등성: 같은 실행 정의의 중복 요청은 기존 Run을 반환하고, 명시적인 재실행은 새 attempt로 구분한다.

### 7.3 SubmitFeedback

- 필수 입력: Tenant, Subject, Request, Feedback Target, 유형 또는 값
- 성공 결과: Feedback 참조와 상태
- 거부 조건: 대상 없음, Tenant 불일치, 허용되지 않은 대상 유형
- 멱등성: 같은 피드백 제출의 중복 기록을 방지하되 사용자의 새로운 평가 변경은 별도 관계로 보존한다.

### 7.4 외부에 요구하는 Operation

| 대상 | 요구 Operation | 기대 결과 |
|---|---|---|
| RAG Runtime | ExecuteEvaluationQuery | 평가용 검색·Evidence·Answer·Citation 결과 |
| 외부 평가 수단 | EvaluateRetrieval·EvaluateAnswer·EvaluateCitation | 지표 값, 판정, 설명과 적용된 평가 외부 자원 구성정보 |

---

## 8. 오류와 복구

### 8.1 오류 분류

| 분류 | 예시 | 기본 처리 |
|---|---|---|
| 기준 오류 | 비활성·불완전 Dataset, 기대 근거 누락 | Run 시작 전 거부 |
| 대상 오류 | 지식 범위·Runtime 조건 불일치 | 계획 실패 |
| Runtime 오류 | 평가 질문 실행 실패 | Case 실패, 정책에 따라 재시도 |
| Evaluator 오류 | 외부 평가 Timeout·응답 오류 | 해당 지표 실패, 재시도 |
| 결과 오류 | 값 형식·범위·설명 불일치 | 결과 수용 거부 |
| 비교 오류 | Dataset·지표 version 불일치 | 비교 거부 또는 판단 불가 |
| 내부 일관성 오류 | Result와 평가 실행 조건의 관계 누락 | Run 완료 금지 |

### 8.2 복구 원칙

- 같은 평가 실행 조건을 유지하는 재시도와 조건을 변경한 재실행을 구분한다.
- Case 단위 재시도를 지원하되 기존 결과를 덮어쓰지 않는다.
- Evaluator 재시도 시 Runtime 실행 결과를 재사용할 수 있다.
- Runtime 조건을 변경하면 새 Run으로 실행하고 변경된 조건을 별도로 유지한다.
- 부분 결과와 실패 Case를 함께 보존한다.

### 8.3 취소

- 신규 Case 실행을 중단한다.
- 이미 완료된 Case Result를 삭제하지 않는다.
- 진행 중 외부 호출의 실제 취소 지원 여부는 외부 명세에 따른다.
- 취소 후 집계 가능 여부를 명시한다.

---

## 9. 동시성, 멱등성과 일관성

### 9.1 동시성

- Case는 서로 독립적인 범위에서 병렬 실행할 수 있다.
- Dataset version 수정과 활성 Run을 분리한다.
- 같은 Run의 Case Result 집계는 중복 반영되지 않도록 한다.
- 동일 평가 자원의 호출 한도는 실행 정책으로 제어할 수 있어야 한다.

### 9.2 멱등성

- StartEvaluation의 동일 정의와 명시적 재실행을 구분한다.
- Case Execution과 Evaluator 호출 attempt를 각각 식별한다.
- 동일 Case Result의 중복 수용을 방지한다.
- Feedback의 동일 제출과 평가 변경 이력을 구분한다.

### 9.3 업무 일관성 경계

Evaluation Run 완료 경계는 다음을 포함한다.

- Dataset version과 평가 실행 조건
- Case Execution 상태
- 수용된 Case Result
- Metric Result와 제외 Case
- 사용된 평가 수단 참조

RAG Runtime과 외부 평가 수단의 상태는 로컬 원자적 트랜잭션에 포함되지 않는다.

### 9.4 재현성

- Run에 사용한 질문, 기대 결과, 지식 범위와 자원·정책 참조를 유지한다.
- 외부 모델의 비결정성 때문에 동일 결과를 보장하지 않고 동일 조건을 재구성할 수 있도록 한다.
- 평가 수단 version이 달라지면 직접 비교 가능 여부를 판단한다.

---

## 10. Tenant, 보안과 권한

### 10.1 Tenant 격리

- Feedback Target, Dataset, Run과 Result의 Tenant 일치를 확인한다.
- 대화 답변에 대한 Feedback은 Tenant와 대화 소유 Subject가 모두 일치하는 경우에만 수용한다.
- 평가 질문도 Runtime에서 동일 Tenant·Knowledge Scope 제약을 적용한다.
- 다른 Tenant의 Dataset과 결과를 비교하지 않는다.
- 집계·통계에서 Tenant 경계를 유지한다.

### 10.2 평가 데이터 보호

- 운영 질문을 Dataset 후보로 사용할 때 개인정보·민감정보 처리 정책을 적용한다.
- 사용자 피드백의 Subject 참조와 자유 의견을 민감정보로 취급한다.
- 외부 Evaluator에는 평가에 필요한 최소 질문·Answer·Evidence만 전달한다.
- 평가 모델 입력과 결과 원문을 일반 로그에 포함하지 않는다.

### 10.3 권한 경계

RAG는 Tenant 내부의 사용자별 평가정보 권한을 관리하지 않는다.

Dataset 작성·검수, 평가 실행과 결과 조회 같은 관리 기능의 접근 통제는 외부 운영 및 인증 체계가 담당한다.

---

## 11. 관찰성과 운영정보

### 11.1 Trace

- 피드백 수용
- 평가 계획과 평가 실행 조건 확정
- Case 실행
- RAG Runtime 평가 호출
- Evaluator 호출
- 결과 검증·집계
- 선택적 자원 구성 비교 평가

### 11.2 Metric

- Feedback 제출 수와 유형 분포
- Evaluation Run 성공·부분 성공·실패율
- Case 처리량과 지연
- Runtime·Evaluator 실패율
- 지표별 결과 분포
- Dataset·지표별 품질 추이
- 평가 비용·외부 호출량을 표현할 수 있는 사용량

평가 지표 값과 시스템 운영 Metric을 구분한다.

### 11.3 구조화 Log

- Dataset version·검수 상태 변경
- Run·Case 상태 전이
- 평가 실행 조건 참조
- Runtime·Evaluator 호출 결과 분류
- 제외 Case와 부분 완료 사유
- 선택적 Comparison 생성과 호환성 판단

질문·기준답변·Answer·Evidence 원문은 기본 로그에서 제외한다.

### 11.4 운영 상태

- 새 Run 수용 가능 여부
- 실행 중 Run과 적체 Case
- 외부 Evaluator 사용 가능 여부
- 실패·재실행이 필요한 Case

---

## 12. 설정과 확장 지점

### 12.1 설정 범주

- 평가 Dataset과 Case 적용 범위
- 평가 지표·Evaluator 참조
- Case 실행 동시성
- Runtime·Evaluator Timeout과 재시도
- 부분 완료 기준
- 집계 정책과 선택적 비교 정책
- 평가 결과 보존 정책
- Feedback 유형과 검토 정책
- 관찰정보 마스킹 정책

### 12.2 구현 교체 경계

- Feedback Repository
- Dataset Repository
- Evaluation Scheduler
- Runtime Evaluation Client
- Rule-based Evaluator
- External Evaluator Client
- Result Aggregator
- Quality Comparator

### 12.3 확장 지점

- RAGAS 외 다른 평가 Framework
- LLM-as-a-Judge
- 규칙 기반 Citation 검증
- Human Review
- 운영 표본 평가
- 적용 외부 자원 구성에 따른 비용·지연·품질 비교
- 실험 승인 Workflow

---

## 13. 제약과 미결정 사항

### 13.1 확정된 제약

- 평가 실행은 운영 실행과 구분한다.
- 평가 조건과 결과의 추적 관계를 유지한다.
- RAGAS에 종속되지 않는다.
- 자동 생성 기준은 검수 없이 활성화하지 않는다.
- 평가 결과가 운영 설정을 자동 변경하지 않는다.
- Tenant 경계를 평가 결과에 적용한다.
- 자원 구성 비교는 시스템 공통 외부 자원 구성이 적용된 평가 결과를 대상으로 하는 선택적 확장이다.

### 13.2 초기 구현 제외 범위

- 비교 결과 기반 자동 구성 승격·배포
- 평가 기반 실시간 모델 라우팅
- 외부 평가 도구 운영
- 사용자 피드백의 자동 정답화
- 전사 승인 Workflow

### 13.3 미결정 사항

- 초기 평가 지표와 RAGAS 적용 범위
- Dataset 검수 주체와 변경 승인 방식
- 평가 Run의 동시성·비용 한도
- 운영 질문의 Dataset 후보 전환 절차
- 부분 완료 허용 기준
- 평가 결과 보존 기간
- 외부 자원 구성정보 비교 평가의 도입 시점과 운영 적용 의사결정 절차
- Quality Evaluation 초기 공동 배치 대상과 독립 분리 조건

---

## 14. 상위 설계 추적

| 상위 설계 책임 | 상세 설계 반영 |
|---|---|
| Quality | Feedback, Criteria, Run과 Result |
| RAG Runtime 의존 | Evaluation Context와 ExecuteEvaluationQuery |
| External Resource Interface | 교체 가능한 Evaluator Interface |
| 평가와 운영 변경 분리 | 결과 제공과 자동 변경 금지 |
| 측정 가능한 품질 | Dataset, Case, Metric과 재현 가능한 평가 실행 조건 |
| Tenant 중심 격리 | Feedback·Run·Result 불변 규칙 |
| Operations & Observability | 평가 실행 OTel 관찰정보 |

---

## 15. 구현 수용 시나리오

| ID | 시나리오 | 기대 결과 |
|---|---|---|
| QEV-001 | 유효한 Answer에 피드백 제출 | Feedback과 대상 관계 생성 |
| QEV-002 | 다른 Tenant 대상 피드백 | 처리 전 거부 |
| QEV-003 | DRAFT Dataset으로 평가 실행 | 실행 거부 |
| QEV-004 | 정상 Dataset 평가 | Case·Metric 결과와 평가 실행 조건 관계 완전 |
| QEV-005 | Runtime Case 일부 실패 | 부분 완료 정책에 따라 상태·제외 사유 기록 |
| QEV-006 | Evaluator 일시 실패 | Case·지표 단위 재시도 |
| QEV-007 | 같은 Run 요청 반복 | 중복 Run 방지 |
| QEV-008 | 평가 조건 변경 재실행 | 새 Run 생성 및 변경 조건 기록 |
| QEV-009 | 선택적 자원 구성 비교 | 호환되는 외부 자원 구성정보의 지표 변화와 판정 제공 |
| QEV-010 | 선택적 비교의 지표 version 불일치 | 직접 비교 거부 또는 판단 불가 |
| QEV-011 | 평가 완료 | 운영 Conversation·통계·설정 미변경 |
| QEV-012 | 자동 생성 Case 활성화 시도 | 검수 없이는 거부 |

### 15.1 구현 완료 판정

- Feedback과 평가 대상의 Tenant 안전한 관계가 검증되어야 한다.
- 동일 조건의 재시도와 조건을 변경한 재실행이 구분되어야 한다.
- 부분 실패가 성공 지표로 왜곡되지 않아야 한다.
- 평가 결과가 운영 설정을 변경하지 않음이 검증되어야 한다.

---

## 16. 상세 설계 완료 점검

- [x] 피드백·Dataset·Run·Result 책임을 정의했다.
- [x] 운영과 평가 실행 컨텍스트를 분리했다.
- [x] 외부 평가 수단의 교체 가능한 경계를 정의했다.
- [x] 부분 평가와 재시도 원칙을 정의하고 자원 구성 비교를 선택적 확장으로 구분했다.
- [x] Tenant와 평가 데이터 보호 제약을 정의했다.
- [x] 평가와 운영 변경을 분리했다.
- [x] API·DB·제품 결정을 후속 설계로 분리했다.
- [x] 미결정 사항과 구현 수용 시나리오를 기록했다.
