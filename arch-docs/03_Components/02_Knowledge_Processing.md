# Enterprise RAG `Knowledge Processing` 상세 설계

## 1. 목적과 범위

Knowledge Processing은 업무 문서를 수용하고 검색 가능한 지식으로 구성하여 외부 검색 저장소에 게시하며, 문서와 지식의 생명주기를 관리하는 Backend 컴포넌트이다.

본 문서는 다음을 상세화한다.

- Knowledge Base, 원본 문서와 문서 버전의 관리 책임
- 문서 해석, 정규화, Knowledge Unit 구성과 지식 표현 생성
- 지식 게시·갱신·제거와 검색 가능 상태
- 장시간 실행되는 처리 작업의 상태·재처리·부분 실패
- 문서부터 게시된 지식까지의 추적 관계
- 외부 문서 해석·임베딩·검색 저장소 인터페이스

문서 형식별 라이브러리, Chunking·임베딩 알고리즘, Queue 제품, DB Schema와 물리 저장소는 정의하지 않는다.

### 1.1 초기 구현 기준

- 모든 문서는 하나의 Tenant와 Knowledge Base에 속한다.
- 원본 문서를 보존하고, 변경은 Document Version으로 구분한다.
- 문서 처리와 지식 게시를 실시간 질의응답 경로와 분리한다.
- 검색 저장소 반영이 완료되고 검증된 지식만 검색 가능 상태로 전환한다.
- 새 버전 게시 전까지 기존 게시 버전의 검색 가능성을 유지할 수 있어야 한다.
- 실패한 처리는 원본과 성공한 중간 결과를 식별하여 재처리할 수 있어야 한다.

---

## 2. 책임과 경계

### 2.1 핵심 책임

- Knowledge Base와 문서 수용 범위 관리
- 원본 문서, 문서 버전과 변경 관계 관리
- 파일 유효성 및 처리 가능성 판단
- 문서 내용·구조 해석 조정
- 해석 결과의 정규화
- 검색 가능한 Knowledge Unit 구성
- 임베딩 등 Knowledge Representation 생성
- 외부 검색 저장소 게시·갱신·제거
- 처리 작업, 실패와 재처리 상태 관리
- 검색 가능 버전과 게시 상태 관리
- 원본·지식·표현·외부 자원 구성정보 추적
- 선택된 지식 생성 전략과 최종 Publication의 관계 유지
- 전략 선택을 위한 후보별 임시 지식 생성·격리·정리
- 선택된 전략으로 전체 문서의 최종 지식 생성

### 2.2 입력과 출력

| 구분 | 주요 정보 |
|---|---|
| 입력 | Tenant Context, Subject Context, Request Context, Knowledge Base 참조, 원본 문서와 Metadata, 처리 목적, Trace Context |
| 출력 | Document·Version 참조, 처리 작업과 상태, Knowledge Unit·Representation 참조, 게시 결과, 실패·재처리 정보 |

### 2.3 소유하는 판단과 상태

- Knowledge Base의 지식 수용 가능 상태
- Document와 Document Version의 생명주기
- 처리 작업의 단계와 결과
- 문서 해석 결과의 수용 가능 여부
- Knowledge Unit 구성 완료 여부
- Knowledge Representation의 호환성과 생성 상태
- 게시 대상 버전과 검색 가능 버전
- 재처리·제거가 필요한 범위
- 후보별 임시 지식의 준비·정리 상태

### 2.4 의존하는 책임

- 외부 인증·조직 시스템: 검증된 Tenant와 Subject Context
- Resource Manager: 시스템 공통 외부 자원 구성과 호환성 기준
- 원본 문서 저장 수단: 문서 원본 보존과 조회
- 외부 문서 해석 자원: 형식별 내용·구조 해석
- 외부 임베딩 자원: 검색 가능한 지식 표현 생성
- 외부 검색 저장소: 지식 표현 게시·갱신·제거
- 외부 모니터링 시스템: OpenTelemetry 정보 활용

### 2.5 수행하지 않는 역할

- 사용자 질문의 실시간 검색
- 대화, Answer와 Citation 관리
- 문서 내용에 기반한 사용자 답변 생성
- 모델·검색 저장소 자동 선택
- 사용자 인증과 조직 관리
- 품질 평가 기준·결과 관리
- 사용자 후보 선택과 최종 전략 확정
- 벡터DB 인프라 설치와 운영

---

## 3. 내부 구성

### 3.1 내부 모듈

| 내부 모듈 | 주된 책임 |
|---|---|
| Knowledge Request Control | Tenant·Knowledge Base와 요청 목적 검증 |
| Knowledge Base Management | Knowledge Base 식별과 수용 상태 관리 |
| Document Lifecycle Management | 원본 문서, 버전, 변경·삭제 관계 관리 |
| Processing Coordination | 처리 작업 생성, 단계 조정, 상태와 attempt 관리 |
| Document Interpretation | 외부 문서 해석 요청과 결과 수용 |
| Content Normalization | 형식별 해석 결과를 공통 콘텐츠 구조로 정규화 |
| Knowledge Unit Construction | 검색·출처 추적 가능한 지식 단위 구성 |
| Representation Generation | 임베딩 등 검색 표현 생성과 호환성 확인 |
| Knowledge Publication | 검색 저장소 게시·교체·제거와 검색 가능 상태 관리 |
| Knowledge Result Management | 처리 결과, 실패, 추적 관계와 재처리 대상 관리 |
| External Resource Interface | 문서 해석·임베딩·검색 저장소 차이 격리 |
| Knowledge Observability | 처리 단계·외부 호출·오류 관찰정보 제공 |

### 3.2 내부 의존 방향

```text
Knowledge Request Control
        ↓
Knowledge Base Management
        ↓
Document Lifecycle Management
        ↓
Processing Coordination
        ├─→ Document Interpretation
        │      ↓
        │   Content Normalization
        │      ↓
        ├─→ Knowledge Unit Construction
        │      ↓
        ├─→ Representation Generation
        │      ↓
        └─→ Knowledge Publication
               ↓
        Knowledge Result Management

Document Interpretation · Representation Generation · Knowledge Publication
        ↓
External Resource Interface

모든 모듈
        ↓
Knowledge Observability
```

### 3.3 상태 변경 책임

| 상태 | 변경 책임 |
|---|---|
| Knowledge Base | Knowledge Base Management |
| Document·Document Version | Document Lifecycle Management |
| Processing Job·Attempt | Processing Coordination |
| Interpreted Content | Document Interpretation·Content Normalization |
| Knowledge Unit | Knowledge Unit Construction |
| Knowledge Representation | Representation Generation |
| Publication | Knowledge Publication |
| 실패·재처리 관계 | Knowledge Result Management |

### 3.4 내부 Operation 명세

| Operation | 제공 모듈 | 목적 |
|---|---|---|
| ValidateKnowledgeRequest | Knowledge Request Control | Tenant, 대상, 요청 목적과 적용된 외부 자원 구성정보 검증 |
| RegisterDocumentVersion | Document Lifecycle Management | 원본과 새 문서 버전 등록 |
| StartProcessing | Processing Coordination | 처리 작업과 attempt 시작 |
| InterpretDocument | Document Interpretation | 문서 내용과 구조 해석 |
| NormalizeContent | Content Normalization | 공통 콘텐츠 구조 생성 |
| ConstructKnowledgeUnits | Knowledge Unit Construction | 검색·출처 단위 구성 |
| GenerateRepresentations | Representation Generation | 검색 표현 생성 |
| PublishKnowledge | Knowledge Publication | 새 버전 게시와 검색 가능 상태 확정 |
| WithdrawKnowledge | Knowledge Publication | 게시된 지식의 검색 가능 상태 제거 |
| CompleteProcessing | Knowledge Result Management | 처리 결과와 추적 관계 완료 |
| PrepareCandidateArtifacts | Processing Coordination | 대표 범위의 후보별 임시 지식 준비 |
| CleanupCandidateArtifacts | Knowledge Result Management | 전략 선택 종료 후 임시 지식 정리 |
| ApplySelectedStrategy | Processing Coordination | 확정 전략으로 전체 문서 처리와 게시 |

---

## 4. 핵심 정보 모델

### 4.1 정보 정의

| 정보 | 의미 |
|---|---|
| Knowledge Base | 특정 목적의 문서와 지식을 묶는 검색 범위 |
| Document | 업무 문서의 논리적 식별 단위 |
| Document Version | 문서 내용 변경을 구분하는 불변 버전 |
| Source Object | 보존된 원본 파일 또는 원본 콘텐츠 참조 |
| Processing Job | 문서 버전을 지식으로 구성하는 업무 단위 |
| Processing Attempt | 실패·재시도를 구분하는 실행 시도 |
| Interpreted Content | 문서의 텍스트·표·이미지·구조 해석 결과 |
| Normalized Content | 원본 형식과 무관한 공통 콘텐츠 구조 |
| Knowledge Unit | 검색과 Citation에 사용할 최소 지식 단위 |
| Knowledge Representation | Knowledge Unit의 검색 가능한 표현 |
| Publication | 특정 문서 버전의 지식을 검색 저장소에 반영한 결과 |
| 처리 외부 자원 구성정보 | 문서 해석·임베딩·검색 저장소와 정책 참조 |

### 4.2 정보 관계

```text
Knowledge Base
  └─ Document
      └─ Document Version
          ├─ Source Object
          └─ Processing Job
              └─ Processing Attempt
                  ├─ Interpreted Content
                  ├─ Normalized Content
                  ├─ Knowledge Unit
                  │   └─ Knowledge Representation
                  ├─ Publication
                  └─ 처리 외부 자원 구성정보
```

### 4.3 불변 규칙

- Knowledge Base, Document와 모든 파생 정보는 같은 Tenant에 속한다.
- Document Version은 생성 후 원본 내용이 변경되지 않는다.
- Knowledge Unit은 하나의 Document Version과 원본 위치를 참조한다.
- Knowledge Representation은 생성한 자원·정책·차원 등 호환성 참조를 가진다.
- Publication에는 게시한 Knowledge Unit과 Representation 범위가 식별되어야 한다.
- `AVAILABLE` 문서 버전은 성공하고 검증된 Publication을 가져야 한다.
- 한 Document에서 기본 검색 가능 버전은 동시에 하나만 활성화하는 것을 원칙으로 한다.
- 새 버전 처리 실패가 기존 검색 가능 버전을 자동 제거하지 않는다.
- Secret과 Endpoint 원문은 외부 자원 구성정보에 저장하지 않는다.

### 4.4 구현용 논리 필드

| 정보 | 필수 의미 |
|---|---|
| Knowledge Base | 식별자, Tenant, 이름·목적 참조, 상태, 외부 자원·정책 참조 |
| Document | 식별자, Tenant, Knowledge Base, 논리 문서명, 현재 버전 참조, 상태 |
| Document Version | 식별자, Document, 버전, 원본 참조·해시·형식, 생성 시점 |
| Processing Job | 식별자, 대상 버전, 목적, 상태, 현재 단계, 생성·완료 시점 |
| Processing Attempt | Job, attempt 번호, 상태, 오류 분류, 시작·종료 시점 |
| Knowledge Unit | 식별자, 대상 버전, 순서·계층, 원본 위치, 내용 참조 |
| Representation | Knowledge Unit, 표현 유형, 자원·정책·호환성 참조 |
| Publication | 대상 버전, 저장소·위치 참조, 상태, 게시·철회 시점 |

---

## 5. 상태와 생명주기

### 5.1 Document Version 상태

```text
RECEIVED
  → PROCESSING
  → READY_TO_PUBLISH
  → PUBLISHING
  → AVAILABLE
  ├─ SUPERSEDED
  └─ WITHDRAWN

RECEIVED · PROCESSING · READY_TO_PUBLISH · PUBLISHING
  → FAILED
```

| 상태 | 의미 |
|---|---|
| RECEIVED | 원본과 Metadata 수용 완료 |
| PROCESSING | 해석·정규화·지식 구성·표현 생성 중 |
| READY_TO_PUBLISH | 게시 대상 결과 검증 완료 |
| PUBLISHING | 검색 저장소 반영 중 |
| AVAILABLE | 검색 가능 상태 확정 |
| SUPERSEDED | 새 버전으로 대체되어 기본 검색 대상에서 제외 |
| WITHDRAWN | 삭제·철회 요구로 검색 불가 |
| FAILED | 처리 또는 게시 실패 |

### 5.2 Processing Job 상태

```text
PENDING
  → RUNNING
  ├─ SUCCEEDED
  ├─ FAILED
  └─ CANCELLED
```

단계 정보는 `VALIDATION`, `INTERPRETATION`, `NORMALIZATION`, `UNIT_CONSTRUCTION`, `REPRESENTATION`, `PUBLICATION`의 의미를 표현할 수 있어야 한다.

상태와 단계의 구체적인 코드 구성은 API·데이터 설계에서 확정한다.

### 5.3 Publication 상태

```text
PREPARING
  → APPLYING
  → VERIFIED
  → ACTIVE
  → RETIRED

PREPARING · APPLYING · VERIFIED
  → FAILED
```

`ACTIVE` 전환은 검색 저장소 반영 결과와 Tenant·Knowledge Base 범위 검증 후 수행한다.

### 5.4 금지되는 상태 전이

- `FAILED → AVAILABLE` 직접 전이
- `WITHDRAWN → AVAILABLE` 기존 버전 직접 복구
- `SUPERSEDED → PROCESSING` 기존 결과 덮어쓰기
- 검증되지 않은 Publication의 `ACTIVE` 전환
- 다른 Tenant 또는 Knowledge Base로 Document Version 이동

재처리는 새 Processing Attempt 또는 새 Document Version으로 표현한다.

### 5.5 상태 전이 구현 규칙

- 상태 변경은 현재 상태와 대상 version을 조건으로 수행한다.
- 외부 저장소 반영 요청 성공만으로 `AVAILABLE`을 기록하지 않는다.
- 새 버전 활성화와 기존 버전 대체 관계는 업무적으로 한 번만 확정한다.
- 중간 결과 재사용 시 원 attempt와 사용 범위를 추적한다.
- 제거 요청은 검색 저장소 결과와 로컬 Publication 상태를 각각 기록한다.

---

## 6. 주요 처리 흐름

### 6.1 신규 문서 처리

```text
RegisterDocument
  → Tenant·Knowledge Base·파일 검증
  → 원본 보존과 Document Version 생성
  → Processing Job 시작
  → 문서 해석
  → 콘텐츠 정규화
  → Knowledge Unit 구성
  → Knowledge Representation 생성
  → 게시 전 완전성·호환성 검증
  → 검색 저장소 게시
  → 게시 결과 검증
  → Document Version AVAILABLE
```

### 6.2 문서 새 버전

```text
새 원본 수용
  → 새 Document Version 처리
  → 기존 AVAILABLE 버전 유지
  → 새 버전 Publication 검증
  → 새 버전 ACTIVE
  → 기존 버전 SUPERSEDED·Publication RETIRED
```

전환 중 사용자가 어느 버전을 검색하는지 불명확한 상태가 발생하지 않도록 활성 버전 교체 경계를 유지한다.

### 6.3 지식 생성 전략 선택 지원

```text
대표 문서 범위와 후보 전략 수용
  → 후보별 임시 Knowledge Unit·Representation 생성
  → 후보별 검색 범위 격리
  → 운영 검색 비노출
  → 사용자 최종 확정 수용
  → 선택 전략으로 전체 문서 재처리
  → 최종 Publication 게시
  → 임시 후보 결과 정리
```

임시 후보 결과를 최종 Publication으로 직접 승격하지 않는다.

### 6.4 재처리

- 재처리 사유와 시작 단계를 명시한다.
- 원본과 이전 중간 결과의 무결성을 확인한다.
- 외부 자원 또는 정책 변경으로 표현이 바뀌면 새 Representation과 Publication을 생성한다.
- 기존 활성 지식은 새 게시 검증 전까지 유지한다.
- 재처리 결과는 이전 attempt를 덮어쓰지 않는다.

### 6.5 문서 철회·삭제

```text
WithdrawDocument
  → Tenant·대상·현재 상태 확인
  → 새 검색 유입 차단
  → 검색 저장소 지식 제거 또는 비활성화
  → Publication RETIRED
  → Document Version WITHDRAWN
  → 원본·업무정보 보존 정책 적용
```

삭제는 검색 제거, 업무 Metadata와 원본의 보존·파기를 구분한다.

### 6.6 부분 실패

- 일부 Knowledge Unit 표현 생성 실패: 전체 게시 가능 여부를 정책으로 판단하되 누락 범위를 기록한다.
- 일부 게시 실패: `AVAILABLE` 전환을 금지하고 적용 범위를 복구·재처리한다.
- 새 버전 실패: 기존 활성 버전을 유지한다.
- 철회 중 외부 저장소 실패: 로컬 철회 의도와 외부 잔여 상태를 추적하고 검색 경로에서 방어한다.

---

## 7. 컴포넌트 Operation 명세

### 7.1 제공 Operation

| Operation | 목적 | 상태 변경 |
|---|---|---|
| CreateKnowledgeBase | 지식 범위 생성 | Knowledge Base 생성 |
| GetKnowledgeBase | 지식 범위와 상태 조회 | 없음 |
| RegisterDocument | 원본 문서와 새 버전 수용 | Document·Version 생성 |
| GetDocument | 문서, 버전과 처리 상태 조회 | 없음 |
| StartDocumentProcessing | 문서 버전 처리 시작 | Job 생성·상태 변경 |
| RetryDocumentProcessing | 실패 실행 재처리 | 새 Attempt 생성 |
| WithdrawDocument | 지식 검색 철회 | Publication·Version 변경 |
| GetProcessingStatus | 처리 단계·실패·게시 상태 조회 | 없음 |
| PrepareCandidateArtifacts | 대표 범위의 후보별 임시 지식 준비 | 후보 Artifact 생성·변경 |
| CleanupCandidateArtifacts | 선택 종료 후보의 임시 지식 정리 | 후보 Artifact 변경 |
| ApplySelectedStrategy | 확정 전략으로 전체 문서 처리·게시 | Job·Publication 생성·변경 |

### 7.2 RegisterDocument

- 필수 입력: Tenant, Subject, Request, Knowledge Base, 원본, 문서 Metadata, Trace Context
- 성공 결과: Document와 Document Version 참조, 처리 수용 상태
- 거부 조건: Tenant·Knowledge Base 불일치, 지원하지 않는 형식·크기·잠금, 적용 가능한 공통 자원 구성 부재
- 멱등성: 동일 Tenant, Knowledge Base와 원본 식별 범위에서 중복 버전 생성을 방지한다.

### 7.3 StartDocumentProcessing

- 필수 입력: Tenant, Document Version, 처리 목적
- 성공 결과: Processing Job 참조와 초기 상태
- 거부 조건: 원본 없음, 이미 완료된 동일 처리, 비활성 Knowledge Base, 자원 호환성 불일치
- 멱등성: 동일 처리 목적과 version의 활성 Job을 중복 생성하지 않는다.

### 7.4 외부에 요구하는 Operation

| 외부 역할 | 요구 Operation | 기대 결과 |
|---|---|---|
| 원본 저장 수단 | StoreSource·LoadSource | 무결성 검증 가능한 원본 참조 |
| 문서 해석 자원 | InterpretSource | 구조와 원본 위치가 유지된 해석 결과 |
| 임베딩 자원 | CreateKnowledgeRepresentation | 검색 저장소와 호환되는 표현 |
| 검색 저장소 | ApplyKnowledge·RemoveKnowledge·VerifyPublication | Tenant·Scope가 적용된 게시·제거 결과 |

---

## 8. 오류와 복구

### 8.1 오류 분류

| 분류 | 예시 | 기본 처리 |
|---|---|---|
| 수용 오류 | 형식·크기·잠금·무결성 오류 | Version 처리 전 거부 |
| Context 오류 | Tenant·Knowledge Base 불일치 | 요청 거부 |
| 해석 오류 | 손상 문서, OCR·Parser 실패 | Job 실패 또는 지원 가능한 범위 기록 |
| 표현 오류 | 임베딩 실패, 호환성·차원 불일치 | 게시 금지 |
| 게시 오류 | 일부 반영, Timeout, 검증 불일치 | AVAILABLE 금지, 복구·재처리 |
| 철회 오류 | 외부 저장소 잔여 데이터 | 철회 의도 유지, 재시도·검색 방어 |
| 내부 일관성 오류 | Unit-원본 위치 관계 누락 | 다음 단계 진행 금지 |

### 8.2 복구 원칙

- 단계별 성공 결과와 외부 자원 구성정보를 유지한다.
- 무결성이 확인된 중간 결과만 재사용한다.
- 외부 호출 재시도는 같은 attempt 안의 호출 시도로 구분한다.
- 업무 재처리는 새 attempt로 구분한다.
- 부분 게시 상태를 성공으로 숨기지 않는다.
- 복구할 수 없는 호환성 오류는 새 처리 정책·자원 결정 후 재처리한다.

### 8.3 보상과 정리

- 새 Publication 검증 실패 시 새로 반영된 범위를 비활성화하거나 제거한다.
- 기존 활성 Publication은 새 버전 검증 실패로 제거하지 않는다.
- 원본 저장 성공·Metadata 저장 실패 시 고아 원본을 식별해 정리할 수 있어야 한다.
- 철회 성공·로컬 상태 실패 시 외부 결과를 조회해 상태를 회복한다.

---

## 9. 동시성, 멱등성과 일관성

### 9.1 동시성

- 같은 Document Version에 상충하는 활성 Processing Job을 허용하지 않는다.
- 같은 Document의 복수 새 버전 처리는 순서 또는 게시 우선순위를 가져야 한다.
- 게시와 철회가 동시에 실행되지 않도록 대상 Publication 단위로 조정한다.
- 다른 Document는 독립적으로 처리할 수 있다.

### 9.2 멱등성

- 원본 해시만으로 Tenant와 Knowledge Base 경계를 대체하지 않는다.
- 동일 수용 요청은 같은 Document Version을 반환할 수 있어야 한다.
- 검색 저장소 게시·제거 요청에는 중복 적용을 식별할 키가 필요하다.
- 동일 키에 다른 원본이나 정책 참조가 들어오면 충돌 처리한다.

### 9.3 업무 일관성 경계

로컬 완료 경계는 다음을 포함한다.

- Document Version과 Source Object 관계
- Processing Job·Attempt와 결과 관계
- Knowledge Unit과 원본 위치
- Representation과 자원·정책 참조
- Publication과 활성 버전 관계

외부 원본 저장소와 검색 저장소는 하나의 원자적 트랜잭션에 포함되지 않으며 명시적인 검증·복구 절차를 사용한다.

### 9.4 RAG Runtime과의 일관성

- Runtime은 실행에 적용된 외부 자원 구성정보와 호환되며 활성 Publication에 속한 지식만 검색한다.
- 하나의 검색 범위에는 실행에 적용된 임베딩 구성정보와 호환되는 Publication만 포함할 수 있다.
- Knowledge Processing은 Runtime 질의마다 상태를 제공하지 않는다.
- 임베딩 구성이 변경되면 Tenant와 Knowledge Base별로 새 Publication을 준비하고 호환성을 확인한다.
- 기존 Publication은 새 Publication이 사용 가능한 상태가 되기 전까지 활성 상태를 유지한다.
- 새 Publication이 준비되면 활성 대상을 전환하고 문제가 발생하면 이전 Publication으로 복원할 수 있어야 한다.
- 철회 지연이 있어도 Runtime이 비활성 지식을 거부할 수 있는 최소 참조가 필요하다.

---

## 10. Tenant, 보안과 권한

### 10.1 Tenant 격리

- 원본 저장 경로·Metadata·처리 작업·검색 저장소 게시 범위에 Tenant를 적용한다.
- Knowledge Base와 Document 관계를 요청마다 확인한다.
- 외부 자원 호출에 필요한 범위만 전달한다.
- 검색 저장소 게시·제거 결과의 Tenant와 Scope를 재검증한다.

### 10.2 파일 안전성

- 파일 확장자만으로 형식을 신뢰하지 않는다.
- 악성 파일 검사 결과와 처리 가능 상태를 수용할 경계를 둔다.
- 암호화·잠금·손상 문서는 정책에 따라 거부 또는 별도 실패 처리한다.
- 문서 해석 실행 환경과 원본 저장 영역의 신뢰 경계를 분리할 수 있어야 한다.

악성 파일 검사 제공 주체와 격리 방식은 보안·물리 설계에서 결정한다.

### 10.3 민감정보

- 원본과 추출 콘텐츠는 업무 민감정보로 취급한다.
- 외부 문서 해석·임베딩 자원에 필요한 콘텐츠만 전달한다.
- Secret, 인증 Header와 Endpoint 원문을 Metadata와 로그에 저장하지 않는다.
- 삭제·보존·법적 보존 정책은 원본, 파생 콘텐츠와 검색 표현에 각각 적용한다.

---

## 11. 관찰성과 운영정보

### 11.1 Trace

- 문서 수용
- 원본 저장
- 처리 Job과 attempt
- 문서 해석
- 정규화와 Knowledge Unit 구성
- Representation 생성
- 검색 저장소 게시·검증·철회
- 상태 변경과 복구

장시간 처리의 Trace 분할·연결 방식은 OTel 상세 설계에서 결정한다.

### 11.2 Metric

- 문서 수용·처리 성공률
- 단계별 처리 시간과 실패율
- 파일 형식별 처리 분포
- 생성된 Knowledge Unit 수
- 외부 자원 호출 성공률과 지연
- 게시·철회 성공률
- 재처리와 부분 실패 비율
- PENDING·RUNNING Job 적체량

### 11.3 구조화 Log

- 문서·버전·Job 수용
- 단계 및 상태 전이
- 오류 분류와 재처리 사유
- 외부 호출 attempt
- 게시 검증과 활성 버전 교체
- 철회와 정리 결과

문서명·원문·추출 콘텐츠는 기본 로그에서 제외하거나 마스킹한다.

### 11.4 운영 상태

- 컴포넌트가 새 처리 요청을 수용할 수 있는 상태
- 기존 Job을 계속 처리할 수 있는 상태
- 역할별 외부 자원 사용 가능 상태
- 처리 적체와 실패 재처리 필요 상태

구체적인 Probe와 운영 API는 후속 설계에서 정의한다.

---

## 12. 설정과 확장 지점

### 12.1 설정 범주

- 허용 파일 형식과 크기
- 문서 해석 정책 참조
- 정규화와 Knowledge Unit 구성 정책 참조
- 임베딩 자원과 호환성 참조
- 검색 저장소와 게시 범위 참조
- 단계별 Timeout·재시도 정책
- 부분 결과 허용 정책
- 보존·삭제 정책 참조
- 작업 동시성·우선순위
- 관찰정보 마스킹 정책

### 12.2 구현 교체 경계

- Source Object Store
- Document Interpreter
- Content Normalizer
- Knowledge Unit Builder
- Embedding Client
- Search Store Publisher
- Document·Job Repository
- Processing Scheduler

구체적인 제품과 동기·비동기 실행 방식은 후속 설계에서 결정한다.

### 12.3 확장 지점

- 새로운 문서 형식
- 표·이미지·멀티모달 지식 구성
- 문서별 Knowledge Unit 전략
- 증분 처리와 변경 부분만 재게시
- 다중 Representation
- 문서 처리 품질 검증
- 대규모 일괄 수용

---

## 13. 제약과 미결정 사항

### 13.1 확정된 제약

- 원본 문서와 변경 버전을 추적한다.
- Tenant와 Knowledge Base를 모든 처리·게시 범위에 적용한다.
- 검증된 게시 결과만 검색 가능 상태로 전환한다.
- 새 버전 실패 시 기존 활성 버전을 유지한다.
- 외부 자원을 자동 선택하거나 운영하지 않는다.
- 후보별 임시 지식을 운영 검색에 노출하거나 최종 지식으로 직접 승격하지 않는다.
- Runtime 실시간 질의 경로에 직접 참여하지 않는다.

### 13.2 초기 구현 제외 범위

- 외부 지식의 자동 수집
- 웹 Crawling
- 모델 학습과 Fine-tuning
- 벡터DB 인프라 운영
- 자동 품질 평가 결과에 따른 재게시

### 13.3 미결정 사항

- 초기 지원 파일별 상세 처리 수준
- 악성 파일 검사와 격리 책임
- 처리 실행의 동기·비동기 및 Queue 방식
- 문서 해석·Knowledge Unit·임베딩 기본 정책
- 부분 Knowledge Unit 성공 허용 여부
- 활성 버전 교체와 검색 가시성 보장 방식
- 원본·파생 콘텐츠·표현의 보존과 삭제 정책
- 대용량 파일과 Batch 처리 한계
- Job 취소 지원 여부

---

## 14. 상위 설계 추적

| 상위 설계 책임 | 상세 설계 반영 |
|---|---|
| Knowledge | 문서 생명주기, 지식 구성, 표현 생성과 게시 |
| 지식 생성 전략 선택 | 후보별 임시 지식 준비·정리와 선택 전략의 전체 문서 적용 |
| External Resource Interface | 문서 해석·임베딩·검색 저장소 접점 |
| 정보 소유권 | Document부터 Publication까지 Knowledge Processing 소유 |
| 실시간 경로 분리 | Runtime 직접 호출 없는 게시 기반 관계 |
| Tenant 중심 격리 | 원본·작업·지식·게시 범위 불변 규칙 |
| 추적 가능한 결과 | 원본→버전→Unit→Representation→Publication 관계 |
| Operations & Observability | Job 상태와 OTel 관찰정보 |

---

## 15. 구현 수용 시나리오

| ID | 시나리오 | 기대 결과 |
|---|---|---|
| KNP-001 | 정상 문서 등록·처리 | AVAILABLE 버전과 활성 Publication 생성 |
| KNP-002 | 동일 수용 요청 반복 | 중복 Version 없이 기존 결과 반환 |
| KNP-003 | 다른 Tenant의 Knowledge Base 지정 | 처리 전 거부 |
| KNP-004 | 문서 해석 실패 | FAILED Job, 원본·원인·재처리 관계 유지 |
| KNP-005 | 임베딩 호환성 불일치 | 게시 금지 |
| KNP-006 | 일부 게시 실패 | AVAILABLE 전환 금지, 복구 대상 기록 |
| KNP-007 | 새 버전 처리 실패 | 기존 활성 버전 검색 가능 유지 |
| KNP-008 | 새 버전 게시 성공 | 새 버전 활성화, 기존 버전 대체 |
| KNP-009 | 문서 철회 | 검색 대상 제거와 상태 추적 |
| KNP-010 | 철회 중 외부 저장소 실패 | 철회 의도 유지, 재시도·검색 방어 가능 |
| KNP-011 | 실패 Job 재처리 | 새 attempt로 실행하고 이전 결과 보존 |
| KNP-012 | 로그·Trace 검사 | 문서 원문·Secret 미포함 |

### 15.1 구현 완료 판정

- 문서부터 게시 결과까지의 추적 관계를 검증할 수 있어야 한다.
- 새 버전 실패와 부분 게시에서 기존 검색 가용성이 보호되어야 한다.
- Tenant 교차 처리와 게시가 차단되어야 한다.
- 장시간 실행 상태, 재처리와 외부 호출이 관찰 가능해야 한다.

---

## 16. 상세 설계 완료 점검

- [x] 문서·지식·게시 책임과 경계를 정의했다.
- [x] 내부 모듈, 상태와 생명주기를 정의했다.
- [x] 신규·버전 변경·재처리·철회 흐름을 정의했다.
- [x] 게시 부분 실패와 활성 버전 일관성 원칙을 정의했다.
- [x] 의미적 Operation과 외부 자원 요구를 정의했다.
- [x] Tenant, 파일 안전성과 민감정보 제약을 정의했다.
- [x] API·DB·제품 결정을 후속 설계로 분리했다.
- [x] 미결정 사항과 구현 수용 시나리오를 기록했다.
