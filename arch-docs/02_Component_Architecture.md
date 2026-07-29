# Enterprise RAG Component Architecture

## 1. 문서 목적

본 문서는 [Enterprise RAG Logical Architecture](./01_Logical_Architecture.md)에서 정의한 논리 영역과 책임을 소프트웨어 구성 단위에 배치한다.

본 문서의 목적은 다음과 같다.

- Enterprise RAG를 구성하는 소프트웨어 컴포넌트를 식별한다.
- 각 컴포넌트의 책임과 책임 경계를 명확하게 한다.
- Logical Architecture의 책임을 소프트웨어 컴포넌트에 배치한다.
- 컴포넌트가 주고받는 정보와 결과 및 상호 의존 관계를 정의한다.
- 외부 시스템과 상호작용하는 컴포넌트 경계를 정의한다.
- Tenant 격리, 근거 기반 답변, 품질 평가와 관찰성 원칙의 컴포넌트별 적용 기준을 제공한다.

본 문서에서 정의하는 컴포넌트는 책임을 구현하는 소프트웨어 구성 단위이다.

컴포넌트는 서비스, 프로세스, 컨테이너 또는 독립 배포 단위와 일치할 수 있지만 반드시 같지는 않다.

---

## 2. 설계 범위

### 2.1 포함 범위

본 문서에서는 다음 내용을 정의한다.

- Enterprise RAG의 소프트웨어 컴포넌트
- 컴포넌트별 책임과 책임 경계
- 논리 영역과 컴포넌트의 매핑
- 컴포넌트 간 의존 관계
- 컴포넌트 간 주요 정보 흐름
- Frontend 기능과 Backend 책임의 관계
- 외부 요청 및 외부 자원 접점
- 공통 실행 컨텍스트와 관찰정보 적용 범위
- 배포 단위로 분리할 수 있는 후보 경계

### 2.2 제외 범위

본 문서에서는 다음 내용을 결정하지 않는다.

- 컴포넌트 내부의 클래스와 모듈 구조
- API 경로, 요청·응답 Schema와 오류 코드
- 데이터 엔티티, 테이블과 물리 저장소
- 동기·비동기 통신 방식
- 메시지와 이벤트 형식
- 처리 상태와 상태 전이
- 재시도, 복구와 보상 정책
- 검색, Chunking, Grounding과 평가 알고리즘
- 서비스 및 컨테이너의 실제 배포 수량
- 네트워크, 포트, 프로토콜과 제품
- 확장성, 가용성과 장애 조치 구성
- OpenTelemetry의 Span, Metric, Log와 전달 토폴로지

---

## 3. 설계 기준

### 3.1 책임 응집도

하나의 컴포넌트는 함께 변경되고 함께 운영될 가능성이 높은 책임을 소유한다.

지식 구성, 실시간 질의응답과 품질 평가는 서로 다른 변경 이유와 실행 특성을 가지므로 독립된 컴포넌트 책임으로 구분한다.

### 3.2 업무 경로 분리

실시간 질의응답 경로와 문서 지식화 경로를 분리한다.

문서 처리 지연이나 실패가 실시간 질의응답에 직접 전파되지 않도록 하며, RAG Runtime이 매 질의마다 Knowledge Processing을 호출하는 구조를 기본 관계로 두지 않는다.

### 3.3 외부 결정 준수

모델, 검색 저장소, 프롬프트와 평가 수단은 외부에서 결정한다.

각 Backend 컴포넌트는 자신이 필요한 외부 자원과 `External Resource Interface`를 통해 상호작용하며 외부 자원을 자동 선택하거나 운영하지 않는다.

### 3.4 외부 인증 경계 유지

사용자 인증과 조직 관리는 Enterprise RAG 외부 책임으로 유지한다.

컴포넌트는 외부에서 검증되어 전달된 Tenant와 사용자 컨텍스트를 수용하고, 자신의 정보와 실행 범위에 Tenant 제약을 적용한다.

본 설계에서는 자체 Bootstrap JWT, 사용자 계정, 역할과 조직 관리 컴포넌트를 추가하지 않는다.

### 3.5 평가와 운영 실행의 분리

품질 평가는 운영 질의응답과 동일한 핵심 기능을 사용할 수 있지만 별도의 평가 실행 컨텍스트를 사용한다.

평가 실행이 운영 대화 이력, 사용자 통계와 피드백을 임의로 변경하지 않도록 논리적으로 구분한다.

### 3.6 외부 관찰 중심 운영

각 Backend는 OpenTelemetry 기반 관찰정보를 제공한다.

관찰정보의 저장, 분석, 시각화, 이상 탐지와 경보는 외부 모니터링 시스템이 담당하며 Enterprise RAG 내부에 별도 모니터링 플랫폼을 구성하지 않는다.

---

## 4. 전체 컴포넌트 구조

Enterprise RAG는 다음 소프트웨어 컴포넌트로 구성한다.

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      Enterprise RAG Frontend                                                │
│                     Chat · Knowledge · Strategy Selection · Resource · Quality                               │
└─────────────────────────────────────────────────────┬───────────────────────────────────────────────────────┘
                                                      │
       ┌────────────────────┬──────────────────────────┼──────────────────────────┬────────────────────┐
       ▼                    ▼                          ▼                          ▼                    ▼
┌───────────────┐  ┌──────────────────┐  ┌────────────────────────┐  ┌──────────────────┐  ┌────────────────┐
│ RAG Runtime   │  │ Knowledge        │  │ Knowledge Strategy     │  │ Quality          │  │ Resource       │
│               │  │ Processing       │  │ Selection              │  │ Evaluation       │  │ Manager        │
│ 검색·대화·답변 │  │ 지식 구성·게시    │  │ 전략 비교·선택·확정      │  │ 결과 평가         │  │ 공통 자원 관리   │
└───────────────┘  └──────────────────┘  └───────────┬────────────┘  └──────────────────┘  └────────────────┘
                                                     │
                         ┌───────────────────────────┴───────────────────────────┐
                         ▼                                                       ▼
                  RAG Runtime                                          Knowledge Processing

각 실행 Backend
  → External Resource Interface
  → 지정된 모델 · 프롬프트 · 평가 수단 · 검색 저장소

각 Backend
  → OpenTelemetry 관찰정보
  → 외부 모니터링 시스템
```

Enterprise RAG Frontend, RAG Runtime, Knowledge Processing, Knowledge Strategy Selection, Quality Evaluation 및 Resource Manager는 서로 구분된 책임을 가진 소프트웨어 컴포넌트이다.

Knowledge Strategy Selection은 독립적인 책임 경계를 가지지만 별도 배포를 의미하지 않는다. 초기에는 Knowledge Processing과 공동 배치할 수 있다.

Quality Evaluation은 독립적인 책임 경계를 가지는 컴포넌트이며, 실제 독립 배포 여부는 물리 아키텍처에서 결정한다.

Resource Manager 역시 독립적인 책임 경계를 가지며 실제 배포 형태는 본 문서에서 결정하지 않는다.

---

## 5. 컴포넌트 정의

### 5.1 Enterprise RAG Frontend

Enterprise RAG Frontend는 사용자가 Enterprise RAG 기능과 상호작용하는 Web UI 컴포넌트이다.

#### 주요 책임

- 채팅형 질의응답 화면을 제공한다.
- 답변과 Citation을 함께 표시한다.
- 대화와 메시지 이력을 표시한다.
- Knowledge Base와 문서 관리 화면을 제공한다.
- 지식 생성 전략 후보 비교, 사용자 선택과 최종 확인 화면을 제공한다.
- 시스템 공통 외부 자원 관리 화면을 제공한다.
- 문서 처리 상태와 실패 정보를 표시한다.
- 사용자 피드백 입력을 제공한다.
- 평가 기준, 실행과 결과 화면을 제공한다.
- 선택적 확장 범위에서 자원 구성별 평가 결과 비교 화면을 제공한다.
- 업무 처리 상태를 확인하는 운영 화면을 제공한다.
- 검증된 사용자 세션의 컨텍스트를 Backend 요청에 전달한다.

#### 책임 경계

Enterprise RAG Frontend는 다음 책임을 수행하지 않는다.

- 사용자 인증과 조직 권한 판정
- Tenant 데이터 격리의 최종 강제
- 문서 분석과 지식 구성
- 지식 검색과 답변 생성
- 품질 평가 실행
- 모델, 검색 저장소와 프롬프트 직접 호출
- 모니터링 데이터 저장·분석과 경보

#### 화면 책임

```text
Enterprise RAG Frontend
├─ Chat
├─ Knowledge Management
├─ Knowledge Strategy Selection
├─ Resource Management
├─ Quality Evaluation
└─ Operations
```

초기에는 하나의 Frontend 애플리케이션 안에서 화면 책임을 구분한다.

사용자 집단, 보안 경계 또는 배포 주기가 분리되어야 하는 요구가 확인되면 Frontend 분리를 별도로 검토한다.

### 5.2 RAG Runtime

RAG Runtime은 사용자 질문에 관련된 지식을 검색하고 검색 근거 범위 안에서 대화형 답변과 출처를 제공하는 Backend 컴포넌트이다.

#### 주요 책임

- 사용자 질문과 대화 요청을 수용한다.
- 대화 맥락을 유지한다.
- 동일 Tenant 안에서도 대화 소유 사용자의 대화 이력만 제공한다.
- Tenant와 Knowledge Base 검색 범위를 적용한다.
- 질문에 관련된 지식을 검색한다.
- 검색 결과의 관련성, 유효성과 충분성을 판단한다.
- 답변에 사용할 근거를 구성한다.
- 외부 프롬프트와 생성 자원을 사용해 답변을 생성한다.
- 근거가 부족한 경우 제한 응답을 제공한다.
- 답변과 원본 지식의 Citation을 구성한다.
- 질문, 검색 결과, 답변과 출처의 추적 관계를 유지한다.
- 평가 실행 컨텍스트의 질의응답 요청을 처리한다.

#### 책임 경계

RAG Runtime은 다음 책임을 수행하지 않는다.

- 원본 문서 수용과 문서 생명주기 관리
- 문서 해석, 지식 구성과 검색 저장소 게시
- 모델, 검색 저장소와 프롬프트의 선택·배포·운영
- 평가 기준과 평가 결과 관리
- 평가 결과에 따른 검색·답변 조건 자동 변경
- 사용자 인증과 조직 관리

#### 실행 경로 원칙

RAG Runtime은 실시간 질의마다 Knowledge Processing을 호출하지 않는다.

질의응답에 필요한 검색 가능한 지식과 게시된 최소 참조정보는 RAG Runtime이 실시간 경로에서 사용할 수 있어야 한다.

해당 정보의 저장 위치, 동기화와 최신성 보장 방식은 상세 설계와 데이터 설계에서 결정한다.

### 5.3 Knowledge Processing

Knowledge Processing은 업무 문서를 검색 가능한 지식으로 구성하고 그 생명주기를 관리하는 Backend 컴포넌트이다.

#### 주요 책임

- Knowledge Base와 문서 관련 요청을 수용한다.
- 원본 문서와 변경 관계를 관리한다.
- 지원되는 업무 문서를 지식 구성 대상으로 수용한다.
- 문서 내용과 구조의 해석을 조정한다.
- 검색 가능한 지식 단위와 표현을 구성한다.
- 구성된 지식을 외부 검색 저장소에 반영한다.
- 원본 문서, 구성된 지식과 적용된 외부 자원 구성정보의 관계를 유지한다.
- 문서 변경에 따라 지식을 갱신하거나 제거한다.
- 처리 상태, 실패와 재처리 대상을 관리한다.
- RAG Runtime이 사용할 검색 가능한 지식의 게시 상태를 유지한다.
- 외부 자원 구성과 호환되는 지식 게시 단위를 준비하고 활성 상태를 관리한다.
- 새 게시 단위가 준비된 후 활성 대상을 전환하고 필요 시 이전 게시 단위를 복원한다.

#### 책임 경계

Knowledge Processing은 다음 책임을 수행하지 않는다.

- 사용자 질문에 대한 실시간 검색
- 대화 맥락과 최종 답변 관리
- 생성 답변의 Citation 구성
- 모델과 검색 저장소의 자동 선택
- 품질 평가 기준과 결과 관리
- 사용자 인증과 조직 관리

#### 지원 문서 범위

Knowledge Processing은 다음과 같은 업무 문서를 수용할 수 있는 책임 경계를 가진다.

- 이미지
- Word 문서
- PowerPoint
- Excel
- PDF
- Text
- Markdown
- 그 밖의 지원 대상으로 결정된 업무 문서

문서별 파서, OCR, Chunking과 임베딩 방식은 상세 설계에서 정의한다.

### 5.4 Knowledge Strategy Selection

Knowledge Strategy Selection은 최초 지식 생성 전에 후보 처리·질의·검색 전략을 비교하고 사용자의 선택과 최종 확정을 관리하는 Backend 컴포넌트이다.

#### 주요 책임

- Tenant와 Knowledge Base의 초기 지식 생성 범위를 확인한다.
- 비교할 후보 전략과 동일한 공통 외부 자원 구성정보를 연결한다.
- Knowledge Processing에 후보별 임시 지식 준비를 요청한다.
- RAG Runtime에 후보별 비교 질문 실행을 요청한다.
- 후보 결과, 비교 질문과 사용자 선택의 관계를 유지한다.
- 사용자의 명시적인 최종 확정을 관리한다.
- 선택된 전략으로 전체 지식 생성을 요청한다.
- 선택 종료 후 임시 후보 결과 정리를 요청한다.

#### 책임 경계

- 후보 품질을 자동 판정하거나 최종 전략을 자동 확정하지 않는다.
- 임시 지식과 최종 게시 지식을 직접 생성하지 않는다.
- 검색·답변을 직접 수행하지 않는다.
- 외부 자원을 자동 선택하거나 Tenant별로 할당하지 않는다.
- 운영 답변의 사용자 피드백과 품질 평가를 관리하지 않는다.
- 게시 이후 전략 변경과 기존 지식 재구성을 수행하지 않는다.

### 5.5 Quality Evaluation

Quality Evaluation은 사용자 피드백을 관리하고 운영 또는 평가 실행에서 생성된 검색 결과와 응답의 품질을 평가하는 Backend 컴포넌트이다.

#### 주요 책임

- 검색 결과와 답변에 대한 사용자 피드백을 수용한다.
- 피드백과 평가 대상 결과의 관계를 유지한다.
- 반복 가능한 평가 기준과 평가 대상을 관리한다.
- 평가 실행을 시작하고 상태를 관리한다.
- RAG Runtime을 통해 평가 질문을 실행한다.
- 외부 평가 수단을 사용해 검색과 답변 품질을 평가한다.
- 평가 결과와 실행 당시 조건의 관계를 유지한다.
- 품질 변화와 개선 필요 영역을 식별한다.
- 서로 다른 외부 자원 구성이 적용된 평가 결과의 비교는 선택적 확장으로 지원한다.

#### 책임 경계

Quality Evaluation은 다음 책임을 수행하지 않는다.

- 운영 검색과 답변 조건의 자동 변경
- 평가 결과에 따른 자동 배포
- 평가 도구와 평가 모델의 자동 선택
- RAGAS와 같은 외부 평가 도구의 운영
- 운영 대화와 사용자 피드백의 임의 변경
- 모델, 검색 저장소와 프롬프트의 생명주기 관리

#### 평가 실행 원칙

Quality Evaluation은 평가 목적, 평가 실행 식별정보와 대상 조건을 포함한 평가 실행 컨텍스트로 RAG Runtime을 호출한다.

RAG Runtime은 평가 요청과 운영 사용자 요청을 구분할 수 있어야 한다.

구체적인 컨텍스트 구조와 평가 결과 Schema는 API 및 데이터 설계에서 정의한다.

### 5.6 Resource Manager

Resource Manager는 외부에서 결정된 자원의 참조정보와 적용 구성을 Enterprise RAG 전체에서 공통으로 관리하는 컴포넌트이다.

#### 주요 책임

- 외부 자원 프로파일과 역할을 관리한다.
- 외부 자원 간 호환성 정보를 관리한다.
- 실행 컴포넌트가 공통으로 사용할 외부 자원 구성을 관리한다.
- 구성 변경과 적용 관계를 식별할 수 있는 이력을 유지한다.
- 구성의 활성화, 비활성화 및 이전 구성으로의 복원을 지원한다.
- 지식 게시와 실행 결과가 어떤 구성을 사용했는지 추적할 수 있도록 한다.
- 실제 인증정보와 Secret 값 대신 외부 관리체계의 참조정보를 유지한다.

#### 책임 경계

Resource Manager는 다음 책임을 수행하지 않는다.

- 실행 요청별 외부 자원 자동 선택과 라우팅
- Tenant별 외부 자원 구성 관리
- 외부 모델, 검색 저장소, 프롬프트 및 평가 도구의 배포와 운영
- 외부 자원의 업무 호출 실행
- 지식 구성, 검색, 답변 생성 및 품질 평가
- 사용자 인증, 조직과 역할 관리

외부 자원 관리정보는 Tenant별 업무정보가 아니라 시스템 공통 구성정보이다. 모든 Tenant는 동일한 공통 구성 집합을 참조하고 Tenant별 자원 프로파일이나 할당을 두지 않는다. 구성 전환 기간에는 이전 구성과 새 구성이 공통 구성 이력 안에서 함께 유효할 수 있다.

Resource Manager의 필수 이력 범위는 외부 자원의 역할·식별 참조·적용 관계, 호환성에 영향을 주는 변경, 구성의 적용·적용 종료·복원 관계와 업무 결과에 실제 적용된 구성정보이다. Secret 원문과 교체 이력은 외부 Secret 관리 체계가 책임지고, 일시적인 가용성·지연·오류는 관찰정보로 다룬다. 실행 결과와 호환성에 영향을 주지 않는 설명·표시정보 변경은 필수 이력 범위에 포함하지 않는다.

Resource Manager는 외부 자원의 현재 상태를 직접 조회하여 구성정보와 비교하거나 불일치를 이유로 자동 비활성화하지 않는다. 적용 상태 변경은 외부 운영 체계에서 검증된 명시적인 관리 요청에 따른다. 세부 변경 단위, 보존 기간과 상태 모델은 Resource Manager 상세 설계와 데이터 설계에서 정의한다.

Resource Manager의 관리 기능에 대한 접근 통제는 외부 운영 및 인증 체계가 담당한다.

---

## 6. 논리 영역과 컴포넌트 매핑

| Logical Architecture 영역 | Component Architecture 배치 | 배치 설명 |
|---|---|---|
| Interaction & Context | Frontend와 각 Backend 요청 경계 | 검증된 요청 맥락을 전달하고 각 컴포넌트가 자신의 범위를 확인한다. |
| Knowledge | Knowledge Strategy Selection, Knowledge Processing | 초기 지식 생성 전략을 선택하고 문서에서 검색 가능한 지식을 구성·유지한다. |
| Retrieval | RAG Runtime | 사용자 질문에 관련된 지식과 답변 근거를 구성한다. |
| Conversation & Response | RAG Runtime | 대화 맥락, 답변과 Citation을 관리한다. |
| Quality | Quality Evaluation | 피드백, 평가 기준, 검색 결과와 응답의 평가를 관리한다. 자원 구성 비교는 선택적 확장으로 둔다. |
| Resource Management | Resource Manager | 시스템 공통 외부 자원 구성과 호환성 및 구성 이력을 관리한다. |
| External Resource Interface | 외부 자원을 사용하는 각 Backend | 별도 중앙 컴포넌트로 확정하지 않고 각 책임 소유 컴포넌트의 외부 접점으로 배치한다. |
| Operations & Observability | 모든 Backend의 공통 책임 | 각 실행을 추적하고 OpenTelemetry 관찰정보를 제공한다. |
| Logical Information | 정보 소유 컴포넌트별 배치 | 문서·지식, 대화·응답, 품질·평가와 실행정보의 의미와 생명주기를 해당 컴포넌트가 소유한다. |

Interaction & Context, External Resource Interface, Operations & Observability와 Logical Information은 반드시 독립 배포 컴포넌트로 분리되는 영역이 아니다.

이들은 여러 컴포넌트에 일관되게 적용되거나 책임 소유 컴포넌트 안에 배치되는 논리 책임이다.

---

## 7. 정보 소유권

컴포넌트는 자신이 생성하는 핵심 정보의 의미와 생명주기를 소유한다.

| 정보 범위 | 소유 컴포넌트 | 주요 책임 |
|---|---|---|
| 문서와 문서 버전 | Knowledge Processing | 원본 문서, 변경 관계와 처리 상태 관리 |
| 지식과 지식 표현 | Knowledge Processing | 원본 문서와 검색 가능한 지식의 관계 관리 |
| 지식 게시 상태 | Knowledge Processing | 검색 가능한 지식의 반영·갱신·제거 상태 관리 |
| 후보 전략·비교 과정·사용자 선택·최종 확정 | Knowledge Strategy Selection | 최초 지식 생성 전에 수행되는 전략 선택의 의미와 생명주기 관리 |
| 후보별 임시 지식 | Knowledge Processing | 운영 지식과 격리된 비교용 지식의 생성과 정리 |
| 대화와 메시지 | RAG Runtime | 대화 맥락과 질의응답 관계 관리 |
| 검색 결과와 답변 근거 | RAG Runtime | 질문, 검색 결과와 근거의 관계 관리 |
| 답변과 Citation | RAG Runtime | 생성 답변과 원본 지식의 관계 관리 |
| 사용자 피드백 | Quality Evaluation | 평가 대상 결과와 피드백의 관계 관리 |
| 평가 기준·실행·결과 | Quality Evaluation | 반복 가능한 검색 결과와 응답 평가에 필요한 관계 관리 |
| 외부 자원 프로파일·호환성·구성 이력 | Resource Manager | 시스템 공통 외부 자원 관리정보와 적용 관계 관리 |
| 업무 실행 상태 | 각 책임 소유 Backend | 자신의 처리 상태와 실패 정보 관리 |
| 적용된 외부 자원 구성정보 | 각 책임 소유 Backend | 실행 결과와 Resource Manager가 제공한 공통 구성의 관계 관리 |

본 표는 논리적 소유권을 의미하며 데이터베이스와 저장소의 물리적 분리를 결정하지 않는다.

---

## 8. 컴포넌트 간 의존 관계

기본 의존 방향은 다음과 같다.

```text
Enterprise RAG Frontend
          ├────────→ RAG Runtime
          ├────────→ Knowledge Processing
          ├────────→ Knowledge Strategy Selection
          ├────────→ Quality Evaluation
          └────────→ Resource Manager

Quality Evaluation
          ↓
RAG Runtime

Knowledge Strategy Selection
          ├────────→ Knowledge Processing
          └────────→ RAG Runtime

Resource Manager
          ↓
시스템 공통 외부 자원 구성

RAG Runtime · Knowledge Processing · Quality Evaluation
          ↓
Resource Manager의 공통 구성 참조

Knowledge Processing
          ↓
External Resource Interface
          ↓
문서 해석 · 임베딩 · 검색 저장소

RAG Runtime
          ↓
External Resource Interface
          ↓
임베딩 · 검색 저장소 · 프롬프트 · 생성 자원

Quality Evaluation
          ↓
External Resource Interface
          ↓
외부 평가 수단

각 Backend
          ↓
외부 모니터링 시스템
```

### 8.1 Frontend와 Backend

Frontend는 각 Backend가 제공하는 인터페이스를 통해 해당 책임과 상호작용한다.

Frontend는 Backend의 내부 위치, 외부 모델과 검색 저장소의 위치를 알지 않는다.

구체적인 요청 경로와 API 주소 구성은 API 설계에서 정의한다.

### 8.2 RAG Runtime과 Knowledge Processing

Knowledge Processing은 검색 가능한 지식을 외부 검색 저장소와 관련 정보 범위에 반영한다.

RAG Runtime은 게시된 지식을 사용해 검색과 답변을 수행한다.

지식 생성 전략 선택을 거친 Publication은 선택된 전략 참조를 포함한다. RAG Runtime은 게시된 참조에 따라 검색 전략을 적용하며 실시간 질의마다 Knowledge Strategy Selection을 호출하지 않는다.

RAG Runtime의 실시간 질의응답은 Knowledge Processing의 처리 가용성에 직접 의존하지 않는 것을 기본 원칙으로 한다.

문서 게시 상태나 Knowledge Base 참조정보의 제공 방식은 상세 설계와 데이터 설계에서 결정한다.

### 8.3 Quality Evaluation과 RAG Runtime

Quality Evaluation은 검색과 답변 품질을 평가하기 위해 RAG Runtime의 질의응답 기능을 사용한다.

Quality Evaluation은 RAG Runtime의 검색 알고리즘과 답변 처리 방식을 직접 변경하지 않는다.

평가 대상 조건은 명시적인 평가 실행 컨텍스트로 전달한다.

### 8.4 Backend와 외부 자원

각 Backend는 자신의 책임 수행에 필요한 외부 자원만 사용한다.

외부 자원의 기술적 차이는 컴포넌트의 External Resource Interface 책임에서 격리한다.

Resource Manager는 외부 자원의 공통 구성과 호환성을 관리하고, 각 Backend의 External Resource Interface는 해당 구성에 따라 실제 외부 자원과 상호작용한다.

Resource Manager는 외부 자원 호출을 대신하지 않으며 External Resource Interface는 공통 구성을 임의로 변경하지 않는다.

---

## 9. Frontend 기능과 Backend 매핑

| Frontend 기능 | 책임 Backend | 상호작용 목적 |
|---|---|---|
| Chat | RAG Runtime | 대화 생성, 질문, 스트리밍 또는 완성 답변, 이력과 Citation 조회 |
| Chat Feedback | Quality Evaluation | 답변과 검색 결과에 대한 사용자 피드백 등록 |
| Knowledge Management | Knowledge Processing | Knowledge Base와 문서 수용, 조회, 변경, 제거와 재처리 |
| Knowledge Status | Knowledge Processing | 문서 및 지식 처리 상태와 실패 정보 조회 |
| Knowledge Strategy Selection | Knowledge Strategy Selection | 후보 결과 비교, 사용자 선택과 최종 확정 |
| Resource Management | Resource Manager | 시스템 공통 외부 자원 프로파일, 호환성과 적용 구성 관리 |
| Quality Evaluation | Quality Evaluation | 평가 기준 관리, 실행, 상태와 결과 조회 |
| Resource Comparison | Quality Evaluation | 선택적 확장으로 적용 외부 자원 구성에 따른 평가 결과 비교 |
| Operations | 각 책임 Backend | 업무 처리 상태와 실패·재처리 대상 확인 |

Operations 화면은 Enterprise RAG의 업무 처리 상태를 확인하기 위한 화면이다.

OpenTelemetry 관찰정보의 분석, 대시보드와 경보 화면은 외부 모니터링 시스템의 책임이며 Frontend가 이를 대체하지 않는다.

---

## 10. 주요 컴포넌트 흐름

### 10.1 지식 구성

```text
사용자 또는 업무 시스템
  → Enterprise RAG Frontend 또는 외부 요청자
  → Knowledge Processing
  → Resource Manager의 공통 구성 참조
  → External Resource Interface
  → 외부 문서 해석 및 임베딩 자원
  → Knowledge Processing
  → External Resource Interface
  → 외부 검색 저장소
  → 처리 결과와 게시 상태 반환
```

Knowledge Processing이 지식 구성 흐름과 결과를 책임진다.

Resource Manager와 외부 자원 인터페이스는 지식 구성의 업무 결정을 대신하지 않는다.

### 10.2 지식 생성 전략 선택

```text
Frontend
  → Knowledge Strategy Selection
  → Knowledge Processing의 후보별 임시 지식 준비
  → RAG Runtime의 후보별 검색·답변 실행
  → Frontend의 결과 비교와 사용자 선택
  → Knowledge Strategy Selection의 최종 확정
  → Knowledge Processing의 전체 문서 처리와 최종 게시
  → 임시 후보 결과 정리
```

후보별 임시 지식은 운영 검색에 노출하지 않고, RAG Runtime은 전략 선택 목적과 지정 후보 범위에서만 사용한다. 최종 지식은 임시 결과를 승격하지 않고 선택된 전략으로 전체 문서를 처리하여 생성한다.

### 10.3 검색 및 답변

```text
사용자
  → Enterprise RAG Frontend
  → RAG Runtime
  → Resource Manager의 공통 구성 참조
  → External Resource Interface
  → 외부 임베딩 자원 및 검색 저장소
  → RAG Runtime
  → External Resource Interface
  → 외부 프롬프트 및 생성 자원
  → RAG Runtime
  → 답변과 Citation 반환
```

Knowledge Processing은 실시간 검색 및 답변 흐름에 직접 참여하지 않는다.

### 10.4 사용자 피드백

```text
사용자
  → Enterprise RAG Frontend
  → Quality Evaluation
  → 피드백과 평가 대상 결과 연결
  → 처리 결과 반환
```

사용자 피드백은 품질 개선 판단의 근거이며 운영 설정을 자동 변경하지 않는다.

### 10.5 품질 평가

```text
평가 실행 주체
  → Enterprise RAG Frontend 또는 외부 요청자
  → Quality Evaluation
  → Resource Manager의 공통 구성 참조
  → 평가 실행 컨텍스트
  → RAG Runtime
  → 검색 및 답변 결과
  → Quality Evaluation
  → External Resource Interface
  → 외부 평가 수단
  → 평가 결과 반환
  → 선택적 확장 시 적용 외부 자원 구성에 따른 비교 결과 반환
```

평가 실행은 운영 대화와 구분되며 운영 설정을 자동 변경하지 않는다.

### 10.6 운영 관찰

```text
RAG Runtime · Knowledge Processing · Quality Evaluation · Resource Manager
  → OpenTelemetry 기반 관찰정보
  → 외부 모니터링 시스템
  → 저장 · 분석 · 시각화 · 이상 탐지 · 경보
```

Frontend의 Operations 화면에서 다루는 업무 상태와 외부 모니터링 시스템이 다루는 관찰정보를 구분한다.

---

## 11. 공통 컴포넌트 제약

### 11.1 Tenant 컨텍스트

Tenant 업무를 처리하는 Backend 요청과 컴포넌트 간 상호작용에는 검증된 Tenant 컨텍스트가 유지되어야 한다.

각 Backend는 자신의 정보 조회와 처리에 Tenant 범위를 강제하며 하위 호출에서 Tenant 컨텍스트를 임의로 변경하지 않는다.

Tenant가 없거나 대상 범위와 일치하지 않는 요청은 업무 처리 대상으로 수용하지 않는다.

구체적인 전달 및 신뢰 검증 방식은 API와 보안 상세 설계에서 정의한다.

Resource Manager가 소유하는 외부 자원 관리정보는 Tenant 범위에 속하지 않는 시스템 공통 정보이므로 이 제약의 대상에서 제외한다.

### 11.2 사용자와 조직 컨텍스트

사용자 인증, 조직 구성과 권한의 원천 관리는 외부 시스템이 담당한다.

Enterprise RAG는 감사와 대화 소유권 확인에 필요한 검증된 사용자 참조를 전달받아 사용할 수 있다.

사용자 참조는 Tenant 경계를 대체하지 않으며 Knowledge Base, 문서, 지식 및 평가정보에 대한 사용자별 권한으로 사용하지 않는다.

동일 Tenant의 사용자는 Tenant에 속한 Knowledge Base를 공통으로 사용한다. 대화와 그 하위 질문, 답변 및 Citation은 Tenant와 대화 소유 사용자가 모두 일치하는 경우에만 접근할 수 있다.

### 11.3 실행 및 추적 컨텍스트

업무 요청과 Backend 간 호출에는 실행을 연결할 수 있는 추적 맥락이 유지되어야 한다.

분산 추적정보는 OpenTelemetry와 W3C Trace Context 같은 표준 관찰 컨텍스트를 통해 전달하는 것을 원칙으로 한다.

업무 식별정보와 관찰용 추적 식별정보의 구체적인 구조는 API 및 상세 설계에서 정의한다.

### 11.4 지식 근거

RAG Runtime은 Retrieval 결과가 제공한 근거 범위 안에서만 답변을 생성한다.

검색 근거가 충분하지 않은 경우 제한 응답을 제공하며 대화 이력이나 외부 생성 모델의 일반 지식을 근거로 대체하지 않는다.

### 11.5 외부 자원 구성정보

Resource Manager는 외부에서 결정된 자원에 대한 시스템 공통 구성과 호환성 정보를 관리한다.

각 Backend는 Resource Manager가 제공한 외부 자원 구성정보를 확인하여 사용하고, 실행 결과와 실제 적용된 구성정보의 관계를 유지한다.

컴포넌트는 호환되지 않는 외부 자원을 임의로 조합하거나 자동 전환하지 않는다.

### 11.6 지식 게시 호환성

Knowledge Processing이 생성한 지식 표현과 RAG Runtime의 검색 표현은 공통 외부 자원 구성의 호환 조건을 따라야 한다.

하나의 검색 범위에는 실행에 적용된 임베딩 구성정보와 호환되는 게시 단위만 포함할 수 있다. 서로 호환되지 않는 임베딩 구성이 적용된 게시 단위를 혼합하여 검색하지 않는다.

임베딩 구성이 변경되면 Knowledge Processing은 Tenant와 Knowledge Base별로 새 지식 게시 단위를 준비한다. 기존 게시 단위는 새 게시 단위가 사용 가능한 상태가 되기 전까지 유지한다.

RAG Runtime은 실행에 적용된 외부 자원 구성정보와 호환되며 활성화된 게시 단위만 사용한다. 활성 게시 단위 전환에 문제가 있으면 이전 게시 단위로 복원할 수 있어야 한다.

### 11.7 평가 실행 컨텍스트

Quality Evaluation과 RAG Runtime은 평가 실행을 운영 사용자 요청과 구분한다.

평가 실행은 평가 목적, 대상 조건과 실행 식별정보를 추적할 수 있어야 하며 운영 대화와 통계를 임의로 변경하지 않는다.

### 11.8 관찰정보

각 Backend는 자신의 업무 처리와 외부 자원 호출을 연결할 수 있는 OpenTelemetry 기반 관찰정보를 제공한다.

관찰정보에 문서 원문, 사용자 질문, 답변, 인증정보와 Secret 같은 민감정보를 기본적으로 포함하지 않는다.

구체적인 관찰 속성, 마스킹과 보존 정책은 상세 설계에서 정의한다.

---

## 12. 외부 시스템 경계

| 외부 시스템 | 접점 | Enterprise RAG의 책임 |
|---|---|---|
| 외부 인증 및 조직 시스템 | Frontend와 각 Backend 요청 경계 | 검증된 사용자·Tenant 컨텍스트를 수용하고 내부 처리 범위에 전달 |
| 외부 Secret 관리 시스템 | Resource Manager와 각 Backend의 External Resource Interface | Secret 참조를 관리하고 실행 시 실제 인증정보를 외부에서 사용 |
| 문서 해석 시스템 | Knowledge Processing의 External Resource Interface | 지정된 문서 해석 요청과 결과 수용 |
| 임베딩 모델 제공 시스템 | Knowledge Processing, RAG Runtime의 External Resource Interface | 문서 지식과 질문의 검색 표현 생성 요청 |
| 생성 모델 제공 시스템 | RAG Runtime의 External Resource Interface | 검색 근거 기반 답변 생성 요청 |
| 외부 검색 저장소 | Knowledge Processing, RAG Runtime의 External Resource Interface | 지식 표현 반영과 관련 지식 검색 |
| 프롬프트 관리 시스템 | RAG Runtime의 External Resource Interface | 외부에서 관리되는 프롬프트 사용 |
| 외부 평가 시스템 | Quality Evaluation의 External Resource Interface | 검색 및 답변 평가 요청과 결과 수용 |
| 외부 모니터링 시스템 | 모든 Backend의 관찰정보 경계 | OpenTelemetry 관찰정보 수집과 활용 |

Enterprise RAG는 외부 시스템의 개발, 배포, 운영과 생명주기를 책임지지 않는다.

---

## 13. 배포 후보 경계

Component Architecture는 다음 구성 단위를 배포 후보로 식별한다.

| 구성 단위 | 컴포넌트 성격 | 배포 후보 |
|---|---|---|
| Enterprise RAG Frontend | 사용자 상호작용 | 독립 Frontend 후보 |
| RAG Runtime | 실시간 검색·대화·답변 | 독립 Backend 후보 |
| Knowledge Processing | 문서·지식 구성·게시 | 독립 Backend 후보 |
| Knowledge Strategy Selection | 초기 지식 생성 전략의 비교·선택·확정 | 독립 책임, 초기 공동 배포 후보 |
| Quality Evaluation | 피드백·검색 결과 및 응답 평가 | 독립 Backend 또는 초기 공동 배포 후보 |
| Resource Manager | 시스템 공통 외부 자원 관리 | 독립 또는 공동 배치 후보 |

### 13.1 기본 구성

기본 구성은 하나의 Frontend와 두 개의 필수 Backend 컴포넌트이다.

```text
Enterprise RAG Frontend
  + RAG Runtime
  + Knowledge Processing
  + Knowledge Strategy Selection 책임
  + Resource Manager 책임
```

Quality Evaluation 책임은 유지하되 초기 배포에서는 다른 Backend와 공동 배치할 수 있다.

공동 배치하더라도 책임, 정보 소유권과 인터페이스 경계를 합치지 않는다.

### 13.2 확장 구성

품질 평가의 실행 부하, 변경 주기와 운영 경계가 독립될 필요가 있으면 Quality Evaluation을 별도 배포 후보로 사용한다.

```text
Enterprise RAG Frontend
  + RAG Runtime
  + Knowledge Processing
  + Knowledge Strategy Selection
  + Quality Evaluation
  + Resource Manager
```

실제 독립 배포, 프로세스 수, 확장 단위와 네트워크 구성은 물리 아키텍처에서 결정한다.

---

## 14. 상위 설계 추적성

| Concept Capability | Logical Architecture 영역 | Component Architecture 배치 |
|---|---|---|
| 지식 관리 | Knowledge | Knowledge Strategy Selection, Knowledge Processing |
| 지식 검색 | Retrieval | RAG Runtime |
| 대화 및 답변 | Conversation & Response | RAG Runtime |
| 외부 자원 관리 및 인터페이스 | Resource Management, External Resource Interface | Resource Manager와 외부 자원을 사용하는 각 Backend의 접점 |
| 품질 관리 | Quality | Quality Evaluation |
| 운영 및 관찰 | Operations & Observability | 모든 Backend의 공통 실행·관찰 책임 |
| Tenant 중심 격리 | Interaction & Context 및 공통 적용 | Tenant 업무 요청 경계와 RAG Runtime·Knowledge Processing·Knowledge Strategy Selection·Quality Evaluation |
| 추적 가능한 결과 | Logical Information | 정보 소유권에 따른 각 Backend |

Frontend는 Concept에 새로운 업무 Capability를 추가하지 않으며 외부 사용자 상호작용을 담당한다.

---

## 15. 최종 컴포넌트 구조

```text
Enterprise RAG Frontend
        ├────────→ RAG Runtime
        │           ├─ Retrieval
        │           └─ Conversation & Response
        │
        ├────────→ Knowledge Processing
        │           └─ Knowledge
        │
        ├────────→ Knowledge Strategy Selection
        │           └─ Knowledge의 전략 선택 책임
        │
        ├────────→ Quality Evaluation
        │           └─ Quality
        │
        └────────→ Resource Manager
                    └─ Resource Management

Quality Evaluation
        └────────→ RAG Runtime
                   평가 실행 컨텍스트

Knowledge Strategy Selection
        ├────────→ Knowledge Processing
        │          후보 임시 지식 준비·전체 지식 생성·정리
        └────────→ RAG Runtime
                   후보 비교 실행

RAG Runtime · Knowledge Processing · Quality Evaluation
        ├────────→ Resource Manager의 공통 구성
        │
        ├────────→ External Resource Interface
        │           └─ 외부 자원 구성정보가 참조하는 외부 자원
        │
        ├────────→ 소유 정보
        │
        └────────→ OpenTelemetry 관찰정보
                    └─ 외부 모니터링 시스템
```

본 Component Architecture는 Logical Architecture의 책임을 Frontend, RAG Runtime, Knowledge Processing, Knowledge Strategy Selection, Quality Evaluation과 Resource Manager에 배치한 결과이다.

컴포넌트 책임과 실제 배포 구조를 구분하며 Quality Evaluation과 Resource Manager의 독립 배포 여부는 후속 물리 아키텍처에서 결정한다.

컴포넌트별 내부 구성과 처리 명세는 [컴포넌트 상세 설계](./03_Components/README.md)에서 구체화한다.

후속 설계 과제와 작업 이력은 [WORK_STATUS](../WORK_STATUS.md)에서 관리한다.
