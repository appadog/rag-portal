# Enterprise RAG `Knowledge Strategy Selection` 상세 설계

## 1. 목적과 범위

Knowledge Strategy Selection은 최초 지식 생성 전에 후보 처리·질의·검색 전략의 실제 결과를 비교하고, 사용자가 전체 지식 생성에 적용할 전략을 명시적으로 확정하도록 지원하는 Backend 컴포넌트이다.

이 컴포넌트는 선택 과정과 결정 정보를 소유한다. 임시 지식과 최종 게시 지식은 Knowledge Processing이 생성하고, 후보별 검색·답변·Citation은 RAG Runtime이 생성한다.

### 1.1 초기 구현 기준

- Knowledge Base의 초기 지식 생성 범위에 선택적으로 적용한다.
- 업로드 문서의 대표 범위를 사용한다.
- 청킹, 질의 처리, 검색과 결과 구성 전략을 비교한다.
- 하나의 선택 과정에는 동일한 시스템 공통 외부 자원 구성정보를 적용한다.
- 최종 결정은 사용자가 명시적으로 확정한다.

## 2. 책임과 경계

### 2.1 핵심 책임

- 전략 선택 과정 생성과 종료
- 후보 전략과 비교 범위 관리
- 후보 준비 상태 조정
- 비교 질문과 후보별 실행 관계 관리
- 사용자 후보 선택 기록
- 최종 확정 가능 여부 판단
- 선택된 지식 생성 전략 확정
- 전체 지식 생성 및 임시 결과 정리 요청

### 2.2 입력과 출력

| 구분 | 내용 |
|---|---|
| 입력 | Tenant, Knowledge Base, 대상 문서, 선택 수행 여부, 비교 질문, 사용자 후보 선택과 최종 확정 |
| 출력 | 선택 과정 상태, 후보 상태, 후보별 실행 결과 참조, 사용자 선택 결과, 선택된 지식 생성 전략 |

### 2.3 수행하지 않는 역할

- 문서 해석, 청킹, 임베딩과 지식 게시
- 후보별 검색과 답변 생성
- 자동 품질 판정과 자동 전략 확정
- 운영 답변의 Feedback과 Quality Evaluation
- 외부 자원의 선택·라우팅·호출
- 게시 이후 전략 변경과 기존 지식 재구성

## 3. 내부 구성

| 모듈 | 책임 |
|---|---|
| Selection Context Control | Tenant, Knowledge Base, 요청 목적과 주체 확인 |
| Candidate Management | 후보 전략과 동일 비교 조건 관리 |
| Candidate Preparation Coordination | Knowledge Processing의 임시 후보 준비·정리 요청 |
| Comparison Coordination | 후보별 RAG Runtime 실행과 결과 관계 관리 |
| User Decision Management | 라운드별 선택과 최종 확정 관리 |
| Strategy Application Coordination | 선택된 전략의 전체 지식 생성 요청 |
| Selection Repository | 선택 과정, 후보, 비교와 결정 정보 유지 |
| Selection Observability | 상태, 실패와 외부 요청 관찰정보 제공 |

내부 모듈은 구현 책임 경계이며 클래스나 배포 단위를 의미하지 않는다.

## 4. 핵심 정보 모델

| 정보 | 의미 | 소유 |
|---|---|---|
| Strategy Selection | Tenant와 Knowledge Base의 전략 선택 과정 | Knowledge Strategy Selection |
| Candidate Strategy | 비교할 처리·질의·검색 방법의 조합 | Knowledge Strategy Selection |
| Candidate Artifact Reference | Knowledge Processing이 생성한 임시 지식 참조 | Knowledge Processing 소유, 참조만 유지 |
| Comparison Execution | 질문과 후보별 Runtime 실행의 관계 | Knowledge Strategy Selection |
| Candidate Result Reference | 검색·답변·Citation 결과 참조 | RAG Runtime 소유, 참조만 유지 |
| User Selection | 비교 라운드에서 사용자가 선택한 후보 | Knowledge Strategy Selection |
| Selected Strategy | 최종 확정된 지식 생성 전략 | Knowledge Strategy Selection |
| Publication Reference | 선택 전략으로 생성한 최종 게시 지식 참조 | Knowledge Processing 소유 |

불변 규칙은 다음과 같다.

- 모든 정보에 동일한 Tenant와 Knowledge Base 범위를 유지한다.
- Candidate Artifact는 후보 간 또는 운영 지식과 혼합하지 않는다.
- Selected Strategy는 사용자 최종 확정 없이 생성하지 않는다.
- 임시 결과를 최종 Knowledge Publication으로 직접 승격하지 않는다.
- 사용자 선택은 Quality Feedback으로 저장하지 않는다.

## 5. 상태와 생명주기

선택 과정은 최소한 다음 의미 상태를 구분한다.

```text
CREATED
  → PREPARING
  → COMPARING
  → READY_TO_CONFIRM
  → CONFIRMED
  → APPLYING
  → COMPLETED
```

실패·중단 상태는 다음과 같다.

```text
FAILED
CANCELLED
EXPIRED
```

- 일부 후보 실패는 전체 과정 실패와 구분한다.
- 최종 적용 실패 시 확정된 전략과 실패 원인을 유지한다.
- 취소·만료 시 원본 문서는 유지하고 임시 후보 정리를 요청한다.

세부 상태 전이와 만료 기준은 API·데이터 및 운영 설계에서 정의한다.

## 6. 주요 처리 흐름

### 6.1 선택 기능을 사용하지 않는 경우

```text
지식 생성 요청
  → 사전에 지정된 기본 전략 적용
  → Knowledge Processing 전체 문서 처리
```

### 6.2 후보 준비와 비교

```text
선택 과정 생성
  → 후보 전략 구성
  → Knowledge Processing 후보별 임시 지식 준비
  → 준비된 후보 조회
  → 동일 질문으로 RAG Runtime 후보별 실행
  → 답변·Citation·원문 근거와 처리 결과 제공
```

### 6.3 사용자 선택과 최종 적용

```text
후보별 결과 비교
  → 사용자 후보 선택
  → 필요 시 추가 질문과 비교
  → 사용자 최종 확정
  → Knowledge Processing 전체 문서 처리 요청
  → 최종 Knowledge Publication 확인
  → 임시 후보 정리
```

## 7. 컴포넌트 Operation 명세

| Operation | 목적 |
|---|---|
| StartStrategySelection | 선택 과정과 후보 준비 시작 |
| GetStrategySelection | 과정, 후보와 준비 상태 조회 |
| ExecuteCandidateComparison | 동일 질문의 후보별 Runtime 실행 |
| SubmitCandidateSelection | 현재 비교 결과에 대한 사용자 선택 기록 |
| ConfirmSelectedStrategy | 최종 전략 확정 |
| CancelStrategySelection | 선택 과정 취소와 정리 요청 |

요구 Operation은 다음과 같다.

| 대상 | Operation | 기대 결과 |
|---|---|---|
| Knowledge Processing | PrepareCandidateArtifacts | 후보별 임시 지식 참조와 상태 |
| Knowledge Processing | ApplySelectedStrategy | 전체 문서 처리와 Publication 참조 |
| Knowledge Processing | CleanupCandidateArtifacts | 후보별 정리 결과 |
| RAG Runtime | ExecuteStrategyComparison | 후보별 검색·답변·Citation 결과 |

구체적인 Endpoint, 메시지와 Schema는 API 설계에서 정의한다.

## 8. 오류와 복구

- 후보 준비 실패는 해당 후보 상태와 원인을 유지한다.
- 일부 후보가 준비되어도 비교 가능 조건을 충족하면 진행할 수 있다.
- Runtime 일부 실패는 성공 후보 결과와 함께 표시한다.
- 최종 적용 실패 시 자동으로 다른 후보를 선택하지 않는다.
- 정리 실패는 선택 완료와 구분하여 재처리 대상으로 유지한다.
- 같은 요청의 재시도는 중복 선택 과정이나 중복 최종 적용을 만들지 않아야 한다.

## 9. 동시성, 멱등성과 일관성

- 같은 Knowledge Base의 초기 전략 선택과 최종 게시 충돌을 방지한다.
- 후보 실행과 사용자 선택은 해당 선택 과정이 유효한 동안만 허용한다.
- 최종 확정은 한 번만 성공하며 이후 다른 후보 선택을 허용하지 않는다.
- 전체 지식 생성과 로컬 확정은 하나의 분산 트랜잭션으로 가정하지 않는다.
- 다른 컴포넌트의 완료 상태를 로컬 정보만으로 추정하지 않는다.

## 10. Tenant, 보안과 권한

- 선택 과정과 후보 결과는 Tenant와 Knowledge Base 기준으로 격리한다.
- Tenant 내부 사용자별 Knowledge Base 권한은 관리하지 않는다.
- 실행과 최종 확정 가능 주체는 외부 인증·운영 체계가 결정한다.
- Subject Context는 선택·확정 주체의 감사정보로 사용한다.
- 일반 Conversation의 사용자 소유권 규칙을 전략 선택 과정에 적용하지 않는다.

## 11. 관찰성과 운영정보

- 선택 과정과 상태 전이
- 후보 준비 수, 성공·실패와 처리시간
- 후보별 비교 실행 상태
- 사용자 선택 및 최종 확정
- 전체 지식 적용과 임시 결과 정리 상태

관찰정보에는 문서, 질문, 답변, 원문 근거와 Secret 원문을 포함하지 않는다.

## 12. 설정과 확장 지점

설정 범주는 후보 전략 집합, 대표 범위 정책, 비교 가능 조건, 과정 만료, 임시 결과 정리와 기본 전략 참조이다.

초기 범위에서는 외부 자원 구성정보를 후보별로 변경하지 않는다. 임베딩 Profile 비교, 후보 자동 추천, 적응형 후보 축소와 게시 이후 전략 재선택은 확장 지점으로 둔다.

## 13. 제약과 미결정 사항

### 13.1 확정된 제약

- 최초 지식 생성 전에 선택적으로 수행한다.
- 선택 결과는 Knowledge Base의 초기 지식 생성 범위에 적용한다.
- 사용자 명시적 확정이 최종 결정이다.
- 임시 결과는 운영 검색과 분리한다.
- Quality Evaluation은 필수 실행 경로에 참여하지 않는다.

### 13.2 미결정 사항

- 후보 수와 후보 구성 규칙
- 대표 문서 범위 선정 방식
- 비교 라운드와 최종 확정 세부 규칙
- 임시 결과 만료와 보존 기간
- 후보별 병렬 처리와 상태 전달 방식
- 임시 검색 범위의 물리 격리 방식

## 14. 상위 설계 추적

| 상위 책임 | 상세 설계 반영 |
|---|---|
| 지식 관리 | 후보 전략 비교, 사용자 선택과 최종 확정 |
| Knowledge | 전략 선택과 지식 구성·게시 책임 분리 |
| Tenant 중심 격리 | 선택 과정과 후보별 범위 불변 규칙 |
| 추적 가능한 결과 | 후보, 질문, 결과, 선택, 전략과 Publication 관계 |
| 외부 결정 | 동일한 시스템 공통 외부 자원 구성정보 적용 |

## 15. 구현 수용 시나리오

| ID | 시나리오 | 기대 결과 |
|---|---|---|
| KSS-001 | 선택 기능 생략 | 기본 전략으로 전체 지식 생성 요청 |
| KSS-002 | 정상 후보 비교 | 후보별 격리된 답변·Citation 결과 제공 |
| KSS-003 | 다른 Tenant 후보 참조 | 실행 전 거부 |
| KSS-004 | 일부 후보 준비 실패 | 성공 후보와 실패 원인을 함께 제공 |
| KSS-005 | 사용자 최종 확정 | 선택 전략으로 전체 지식 생성 요청 |
| KSS-006 | 확정 없는 게시 요청 | 거부 |
| KSS-007 | 최종 적용 실패 | 확정 전략과 실패 원인 유지 |
| KSS-008 | 선택 취소 | 원본 유지, 임시 결과 정리 요청 |
| KSS-009 | 운영 지식과 후보 혼합 | 검색 실행 거부 |

## 16. 상세 설계 완료 점검

- [x] 선택 과정과 지식 생성 책임을 분리했다.
- [x] 후보 지식, Runtime 결과와 선택 정보의 소유권을 구분했다.
- [x] 사용자 결정과 Quality Feedback을 구분했다.
- [x] Tenant와 운영 검색 격리 원칙을 정의했다.
- [x] API·DB·물리 격리 결정을 후속 설계로 분리했다.
