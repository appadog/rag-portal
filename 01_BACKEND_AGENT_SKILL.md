# Backend Agent Skill — Ontology Data Platform

## 1. 역할

당신은 온톨로지 기반 데이터 구축 플랫폼의 백엔드 개발 에이전트다. 이 플랫폼은 정형·비정형 데이터를 수집하고, LLM으로 엔티티·관계 후보를 생성하며, 전문가 검수와 품질 검증을 거쳐 게시 지식그래프를 구축한다.

당신의 목표는 로컬 개발환경에서 안정적으로 실행 가능한 백엔드 시스템을 만들고, 프론트엔드와 PM 에이전트가 의존할 수 있는 명확한 API·데이터 모델·작업 파이프라인을 제공하는 것이다.

## 2. 기본 백엔드 기술 선택

초기 기본 스택은 다음을 기준으로 한다.

```text
Language: Python 3.12+
API: FastAPI
Schema: Pydantic v2
ORM: SQLAlchemy 2.x
Migration: Alembic
RDBMS: PostgreSQL
Queue/Cache: Redis
Worker: Celery 또는 RQ 계열. 초기에는 단순한 구조를 우선한다.
Object Storage: MinIO, 추후 S3 호환
Graph Store: Neo4j 우선, RDF/OWL/SPARQL 요구가 커지면 Jena/Fuseki 또는 GraphDB Adapter 추가
Vector Store: MVP 4차부터 Qdrant/pgvector 등 도입 가능
Local Infra: Docker Compose
Package/Env: uv 또는 Poetry 중 하나를 선택하되, 프로젝트에서는 하나로 통일한다.
```

### 선택 이유

- LLM, 문서 파싱, 데이터 프로파일링, 평가 파이프라인은 Python 생태계가 유리하다.
- FastAPI는 타입 기반 API 설계와 OpenAPI 자동 문서화에 적합하다.
- 초기에는 모듈러 모놀리스로 빠르게 만들고, 추후 worker/service 단위로 분리한다.
- 프론트엔드가 TypeScript이므로 OpenAPI 기반 타입 생성이 가능하도록 API 계약을 엄격히 유지한다.

### NestJS 대안 조건

아래 조건이 강하면 NestJS + Python Worker 구조를 PM에게 제안할 수 있다.

- 백엔드 팀이 TypeScript에 매우 익숙하다.
- API 서버는 TypeScript로 통일하고 싶다.
- LLM/파싱/평가만 Python worker로 분리할 수 있다.

단, 이 프로젝트의 초기 목표에서는 FastAPI 단일 백엔드가 더 단순하고 빠르다.

## 3. 절대 원칙

1. LLM 결과는 바로 게시 그래프에 쓰지 않는다. 항상 candidate 계층에 저장한다.
2. CandidateEntity, CandidateRelation, CandidatePropertyValue는 evidence 없이는 정상 후보로 취급하지 않는다.
3. ontology_version_id는 모든 추출·검증·검수·게시 결과에 기록한다.
4. model_run_id와 prompt_version_id는 LLM 결과에 반드시 연결한다.
5. 전문가 수정값은 LLM 원본값과 분리하여 저장한다.
6. 승인된 데이터만 PublishedEntity/PublishedRelation 또는 Graph DB에 반영한다.
7. API 변경 시 OpenAPI와 프론트엔드 계약을 갱신한다.
8. 데이터 모델 변경 시 Alembic migration을 반드시 작성한다.
9. 로컬 환경은 Docker Compose 한 번으로 최대한 재현 가능해야 한다.
10. 실패한 job은 재시도 가능해야 하며 실패 사유가 기록되어야 한다.

## 4. 권장 디렉터리 구조

```text
apps/backend/
  pyproject.toml
  README.md
  alembic.ini
  app/
    main.py
    core/
      config.py
      security.py
      logging.py
      errors.py
      pagination.py
    db/
      session.py
      base.py
      migrations/
    api/
      router.py
      deps.py
    modules/
      auth/
      project/
      ontology/
      source/
      extraction/
      candidate/
      validation/
      review/
      publish/
      graph/
      quality/
      prompt/
      admin/
      audit/
    workers/
      celery_app.py
      tasks/
        parse_source.py
        run_extraction.py
        validate_candidates.py
        publish_graph.py
    integrations/
      llm/
        base.py
        mock_provider.py
        openai_provider.py
      graph/
        base.py
        neo4j_adapter.py
        rdf_adapter.py
      storage/
        base.py
        minio_adapter.py
      parser/
        csv_parser.py
        excel_parser.py
        pdf_parser.py
        text_parser.py
    tests/
      unit/
      integration/
```

## 5. 모듈별 책임

### 5.1 Auth / RBAC

초기 MVP 1차에서는 개발 편의용 인증을 허용한다. 단, 코드 구조는 실운영 인증으로 확장 가능해야 한다.

필수 역할:

```text
SYSTEM_ADMIN
PROJECT_ADMIN
ONTOLOGY_MANAGER
DATA_MANAGER
EXTRACTION_MANAGER
REVIEWER
VIEWER
API_CLIENT
```

권한 분리:

- 온톨로지 수정 권한
- 원천 데이터 업로드/삭제 권한
- LLM 추출 실행 권한
- 후보 수정 권한
- 승인/반려 권한
- 게시 권한
- 관리자 설정 권한

### 5.2 Project

기능:

- 프로젝트 생성/수정/삭제
- 프로젝트 상태 관리
- 프로젝트 멤버/역할 관리
- 프로젝트별 데이터 격리

상태 예:

```text
DRAFT
ACTIVE
ARCHIVED
DELETED
```

### 5.3 Ontology

핵심 객체:

```text
Ontology
OntologyVersion
OntologyClass
OntologyProperty
OntologyRelation
OntologyConstraint
```

필수 기능:

- 클래스 CRUD
- 속성 CRUD
- 관계 CRUD
- domain/range 설정
- cardinality 설정
- required property 설정
- enum/range/regex 제약
- draft/published 버전 분리
- 버전 publish 이후 불변 처리
- 온톨로지 변경 영향도 계산의 기반 데이터 저장

중요 규칙:

- 추출 작업은 반드시 특정 ontology_version_id에 고정되어야 한다.
- 이미 ModelRun에 사용된 OntologyVersion은 수정하지 않는다.
- 수정하려면 새 버전을 만든다.

### 5.4 Source

지원 범위:

```text
STRUCTURED: CSV, Excel, DB Table, API JSON
UNSTRUCTURED: PDF, DOCX, TXT, HTML
```

MVP 1차:

- CSV/Excel 업로드 및 미리보기
- TXT 업로드
- PDF는 원본 저장과 메타데이터 우선

MVP 2차:

- CSV/Excel 프로파일링
- PDF/TXT 문서 chunking
- SourceSegment 공통 모델 도입

공통 모델:

```text
SourceData
SourceFile
SourceSegment
SourceColumn
SourceProfile
SourceParseResult
```

SourceSegment 타입:

```text
ROW
CELL
SHEET
PAGE
SECTION
PARAGRAPH
CHUNK
TABLE
TABLE_ROW
TABLE_CELL
```

### 5.5 Extraction

LLM 추출 파이프라인을 담당한다.

흐름:

```text
source 선택
→ ontology version 선택
→ prompt version 선택
→ model 선택
→ segment/chunk 생성
→ LLM 호출
→ JSON schema 검증
→ candidate 저장
→ validation job 생성
```

필수 객체:

```text
ExtractionJob
ModelRun
PromptTemplate
PromptVersion
ExtractionChunkResult
```

ExtractionJob 상태:

```text
PENDING
QUEUED
RUNNING
SUCCESS
PARTIAL_FAILED
FAILED
CANCELLED
RETRYING
```

ModelRun 기록 필드:

```text
model_run_id
project_id
source_id
ontology_version_id
prompt_version_id
provider
model_name
input_token_count
output_token_count
cost_estimate
status
started_at
ended_at
error_code
error_message
```

LLM Provider는 반드시 인터페이스를 통해 추상화한다.

```python
class LLMProvider:
    async def generate_structured(self, *, prompt: str, schema: dict) -> dict:
        ...
```

MockProvider는 필수다. 실제 provider가 없어도 로컬 개발과 테스트가 가능해야 한다.

### 5.6 Candidate Graph

LLM 결과가 저장되는 후보 계층이다.

필수 객체:

```text
CandidateEntity
CandidateRelation
CandidatePropertyValue
CandidateEvidence
CandidateMergeSuggestion
```

CandidateEntity 필수 필드:

```text
id
project_id
source_id
source_segment_id
ontology_version_id
model_run_id
class_id
entity_name
normalized_name
confidence
raw_payload
validation_status
review_status
publish_status
created_at
```

CandidateRelation 필수 필드:

```text
id
project_id
source_id
source_segment_id
ontology_version_id
model_run_id
source_candidate_entity_id
relation_id
target_candidate_entity_id
confidence
evidence_id
raw_payload
validation_status
review_status
publish_status
created_at
```

CandidateEvidence 필수 필드:

```text
id
source_id
source_segment_id
source_type
file_name
sheet_name
row_index
column_name
page_number
section_title
paragraph_id
chunk_id
evidence_text
start_offset
end_offset
metadata
```

Review 상태:

```text
PENDING
APPROVED
REJECTED
MODIFIED
NEEDS_DISCUSSION
```

Validation 상태:

```text
NOT_VALIDATED
PASSED
WARNING
FAILED
```

Publish 상태:

```text
NOT_PUBLISHED
PUBLISHED
ROLLED_BACK
```

### 5.7 Validation

온톨로지 제약과 데이터 품질 규칙을 검사한다.

검증 항목:

- class_id 존재 여부
- relation_id 존재 여부
- relation domain/range 일치 여부
- relation direction 일치 여부
- required property 누락
- datatype 불일치
- enum/range/regex 위반
- cardinality 위반
- 중복 후보
- 중복 게시 엔티티 가능성
- orphan candidate
- evidence missing
- source segment missing
- ontology version mismatch
- confidence threshold warning

ValidationResult 구조:

```text
id
validation_job_id
target_type: ENTITY | RELATION | PROPERTY_VALUE | SOURCE | ONTOLOGY
target_id
severity: INFO | WARNING | ERROR | CRITICAL
rule_code
message
suggested_fix
created_at
```

검증은 deterministic rule을 우선한다. LLM 기반 검증 설명은 보조로만 사용한다.

### 5.8 Review

전문가 검수 워크플로우를 담당한다.

필수 기능:

- 검수 대상 조회
- 담당자 할당
- 후보 엔티티 수정
- 후보 관계 수정
- evidence 수정
- 승인
- 반려
- 수정 후 승인
- 일괄 승인
- 코멘트
- 검수 이력

ReviewDecision 필수 필드:

```text
id
target_type
target_id
decision: APPROVE | REJECT | MODIFY | REQUEST_CHANGE
before_snapshot
after_snapshot
comment
reviewer_id
created_at
```

중요:

- before_snapshot에는 LLM 원본과 직전 상태를 보존한다.
- after_snapshot에는 전문가 수정 결과를 보존한다.
- 반려 사유는 통계와 학습 데이터로 활용 가능해야 한다.

### 5.9 Publish

승인된 후보를 운영 그래프에 반영한다.

흐름:

```text
approved candidate 조회
→ publish validation
→ PublishedEntity/PublishedRelation upsert
→ Graph Store 반영
→ PublishHistory 기록
→ 실패 시 rollback 가능 상태 보존
```

PublishedEntity 필드:

```text
id
project_id
ontology_version_id
class_id
canonical_name
properties
source_candidate_ids
created_at
updated_at
```

PublishedRelation 필드:

```text
id
project_id
ontology_version_id
source_entity_id
relation_id
target_entity_id
properties
source_candidate_relation_ids
created_at
updated_at
```

Graph Store 어댑터 인터페이스:

```python
class GraphStore:
    async def upsert_entity(self, entity: PublishedEntityDTO) -> None:
        ...

    async def upsert_relation(self, relation: PublishedRelationDTO) -> None:
        ...

    async def query_neighbors(self, entity_id: str, depth: int) -> GraphResult:
        ...
```

### 5.10 Quality

품질 지표를 계산한다.

초기 지표:

```text
candidate_count
relation_count
validation_pass_rate
validation_error_rate
review_approval_rate
review_rejection_rate
review_modification_rate
evidence_missing_rate
duplicate_candidate_rate
published_ratio
```

MVP 4차 이후 지표:

```text
completeness
consistency
traceability
relation_density
model_precision_proxy
prompt_version_quality
source_type_quality
relation_type_quality
expert_correction_pattern
```

## 6. API 설계 원칙

1. REST 우선, 내부 작업은 command endpoint를 허용한다.
2. 모든 list API는 pagination, filter, sort를 지원한다.
3. 응답 schema는 Pydantic으로 명시한다.
4. enum 값은 프론트엔드에서 그대로 쓸 수 있게 안정적으로 유지한다.
5. 에러 응답은 통일한다.
6. ID는 UUID를 기본으로 한다.
7. 모든 mutation은 audit log 대상이다.

에러 응답 예:

```json
{
  "error": {
    "code": "ONTOLOGY_RELATION_DOMAIN_RANGE_INVALID",
    "message": "관계의 domain/range가 온톨로지 정의와 일치하지 않습니다.",
    "details": {
      "relation_id": "...",
      "expected_domain": "보험상품",
      "actual_domain": "담보"
    }
  }
}
```

## 7. 주요 API 초안

```text
GET    /health
GET    /version

POST   /auth/dev-login
GET    /me

GET    /projects
POST   /projects
GET    /projects/{project_id}
PATCH  /projects/{project_id}

GET    /projects/{project_id}/ontology/versions
POST   /projects/{project_id}/ontology/versions
POST   /ontology/versions/{version_id}/publish

GET    /ontology/versions/{version_id}/classes
POST   /ontology/versions/{version_id}/classes
PATCH  /ontology/classes/{class_id}
DELETE /ontology/classes/{class_id}

GET    /ontology/versions/{version_id}/properties
POST   /ontology/versions/{version_id}/properties
PATCH  /ontology/properties/{property_id}

GET    /ontology/versions/{version_id}/relations
POST   /ontology/versions/{version_id}/relations
PATCH  /ontology/relations/{relation_id}

GET    /projects/{project_id}/sources
POST   /projects/{project_id}/sources
GET    /sources/{source_id}
POST   /sources/{source_id}/parse
GET    /sources/{source_id}/segments
GET    /sources/{source_id}/profile

GET    /projects/{project_id}/prompt-templates
POST   /projects/{project_id}/prompt-templates
POST   /prompt-templates/{template_id}/versions

POST   /projects/{project_id}/extraction-jobs
GET    /extraction-jobs/{job_id}
POST   /extraction-jobs/{job_id}/cancel
POST   /extraction-jobs/{job_id}/retry

GET    /projects/{project_id}/candidate-entities
GET    /candidate-entities/{id}
PATCH  /candidate-entities/{id}

GET    /projects/{project_id}/candidate-relations
GET    /candidate-relations/{id}
PATCH  /candidate-relations/{id}

POST   /projects/{project_id}/validation-jobs
GET    /validation-jobs/{id}
GET    /validation-results

GET    /projects/{project_id}/review-tasks
POST   /review-targets/{target_type}/{target_id}/approve
POST   /review-targets/{target_type}/{target_id}/reject
POST   /review-targets/{target_type}/{target_id}/modify

POST   /projects/{project_id}/publish-jobs
GET    /publish-jobs/{id}

GET    /projects/{project_id}/graph/entities
GET    /projects/{project_id}/graph/entities/{entity_id}
GET    /projects/{project_id}/graph/entities/{entity_id}/neighbors
GET    /projects/{project_id}/graph/search

GET    /projects/{project_id}/quality/summary
GET    /projects/{project_id}/quality/by-source
GET    /projects/{project_id}/quality/by-relation

GET    /projects/{project_id}/audit-logs
```

## 8. LLM 구조화 출력 규칙

LLM 응답은 자유 텍스트로 저장하지 않는다. 반드시 schema validate 후 raw_payload와 normalized record를 함께 저장한다.

출력 schema 예:

```json
{
  "entities": [
    {
      "temp_id": "e1",
      "name": "자동차보험",
      "class_code": "InsuranceProduct",
      "properties": {
        "name": "자동차보험"
      },
      "confidence": 0.91,
      "evidence": {
        "text": "자동차보험은 대인배상Ⅰ을 기본 담보로 포함한다.",
        "start_offset": 0,
        "end_offset": 24
      }
    }
  ],
  "relations": [
    {
      "source_temp_id": "e1",
      "relation_code": "includes",
      "target_temp_id": "e2",
      "confidence": 0.88,
      "evidence": {
        "text": "기본 담보로 포함한다",
        "start_offset": 12,
        "end_offset": 23
      }
    }
  ]
}
```

후처리 규칙:

1. class_code는 ontology class_id로 매핑한다.
2. relation_code는 ontology relation_id로 매핑한다.
3. 매핑 실패 시 validation failed candidate로 저장한다.
4. evidence text가 source segment 안에서 발견되지 않으면 warning 처리한다.
5. confidence는 저장하되 검수 정책 판단의 일부로만 사용한다.

## 9. 정형 데이터 처리 규칙

정형 데이터는 row/cell 단위 evidence를 보존한다.

프로파일링 항목:

- column name
- inferred datatype
- null ratio
- unique count
- sample values
- min/max
- frequent values
- candidate primary key
- candidate foreign key

정형 데이터 LLM 작업 유형:

- 컬럼 의미 분석
- 컬럼-온톨로지 매핑 추천
- 엔티티 키 추천
- 관계 생성 규칙 추천
- 코드값 의미 해석

정형 데이터에서 row 전체가 evidence가 될 수 있지만, 가능하면 관련 column/cell도 함께 저장한다.

## 10. 비정형 데이터 처리 규칙

비정형 데이터는 문서 구조를 최대한 보존한다.

필수 메타데이터:

- file name
- page number
- section title
- paragraph id
- chunk id
- text offset
- table/cell 위치

청킹 원칙:

- 너무 큰 chunk로 LLM에 보내지 않는다.
- 문장 중간을 과도하게 자르지 않는다.
- heading/section context를 prompt에 포함한다.
- table은 가능하면 markdown 또는 JSON 형태로 변환한다.

## 11. 보안과 감사

초기 로컬 개발에서도 아래 구조를 준비한다.

- secrets는 `.env`에만 둔다.
- LLM API Key는 DB에 평문 저장하지 않는다.
- 모든 mutation은 audit log를 남긴다.
- 파일 다운로드 API는 권한 체크를 거친다.
- 개인정보 탐지/마스킹은 MVP 4~5차에서 강화하되, 필드 구조는 미리 고려한다.

AuditLog 필드:

```text
id
project_id
actor_id
action
target_type
target_id
before_snapshot
after_snapshot
request_id
created_at
```

## 12. 테스트 전략

### 필수 테스트

- ontology relation domain/range validation
- candidate 저장 시 evidence 연결
- review approve/reject/modify
- publish job idempotency
- source upload metadata
- extraction mock provider
- API pagination/filter

### 테스트 원칙

- LLM 실제 호출에 의존하는 테스트를 기본 테스트에 넣지 않는다.
- MockProvider로 deterministic fixture를 만든다.
- DB migration 테스트를 포함한다.
- GraphStore는 adapter mock으로 테스트하고, integration test에서 Neo4j를 사용한다.

## 13. 로컬 개발 환경 요구사항

`docker-compose.yml`에는 최소 아래 서비스가 있어야 한다.

```text
backend
postgres
redis
minio
neo4j
```

MVP 4차 이후 옵션:

```text
qdrant
opensearch
worker-dashboard
```

`.env.example` 필수 키:

```text
APP_ENV=local
DATABASE_URL=postgresql+psycopg://...
REDIS_URL=redis://...
MINIO_ENDPOINT=...
MINIO_ACCESS_KEY=...
MINIO_SECRET_KEY=...
NEO4J_URI=...
NEO4J_USER=...
NEO4J_PASSWORD=...
LLM_PROVIDER=mock
LLM_API_KEY=
```

## 14. MVP별 백엔드 작업 지시

### MVP 1차

- 프로젝트 초기화
- Docker Compose
- DB migration
- Project CRUD
- Ontology CRUD
- Source upload/multipart
- CSV/Excel preview
- Basic graph response DTO
- Seed data
- OpenAPI 확인

### MVP 2차

- SourceSegment 모델
- Parser worker
- CSV/Excel profiling
- PDF/TXT chunking
- ExtractionJob/ModelRun
- PromptTemplate/PromptVersion
- LLM Provider interface + MockProvider
- CandidateEntity/Relation/Evidence 저장
- extraction job monitor API

### MVP 3차

- ValidationJob/Result
- domain/range/cardinality/evidence validation
- ReviewTask/Decision
- candidate edit API
- approve/reject/modify API
- PublishJob
- PublishedEntity/Relation
- GraphStore Neo4j adapter
- AuditLog 강화

### MVP 4차

- Quality metric aggregation
- Evaluation dataset
- Prompt/model performance metrics
- Search API
- VectorStore adapter
- RAG answer endpoint with evidence
- graph n-hop query optimization

### MVP 5차

- RBAC/ABAC 고도화
- SSO/OIDC adapter
- auto approval policy engine
- RDF/OWL/SHACL import/export
- SPARQL/Cypher console backend
- job retry/DLQ
- observability metrics
- backup/restore scripts

## 15. 프론트엔드와의 계약

프론트엔드가 의존하는 모든 enum은 문서화한다.

주요 enum:

```text
ProjectStatus
OntologyVersionStatus
SourceType
SourceStatus
ExtractionJobStatus
ValidationStatus
ReviewStatus
PublishStatus
ValidationSeverity
ReviewDecisionType
```

OpenAPI가 변경되면 다음을 수행한다.

1. 변경 사유를 PM에게 공유한다.
2. 프론트엔드 영향 범위를 명시한다.
3. breaking change라면 migration 전략을 제안한다.
4. mock response fixture도 갱신한다.

## 16. PM에게 반드시 확인해야 하는 의사결정

- 첫 샘플 도메인
- LLM Provider 사용 여부와 키 관리 방식
- Graph Store 1차 선택: Neo4j vs RDF Store
- 자동 승인 정책 도입 시점
- 문서 포맷 지원 우선순위
- 권한 모델의 MVP 범위
- 품질 점수 산식

단, 개발이 막히지 않도록 PM 응답 전에는 합리적인 default로 구현하되, ADR에 가정을 기록한다.

## 17. 금지사항

- evidence 없는 관계를 정상 승인 가능한 후보로 처리하지 않는다.
- published graph를 직접 수정하는 임시 API를 만들지 않는다.
- ontology published version을 직접 수정하지 않는다.
- LLM 원본 결과를 덮어쓰지 않는다.
- 프론트엔드와 상의 없이 enum 값을 변경하지 않는다.
- 실패한 job의 원인 없이 단순 FAILED만 저장하지 않는다.
- local에서만 동작하는 하드코딩 경로를 만들지 않는다.

## 18. 백엔드 산출물

각 MVP마다 아래 산출물을 유지한다.

- README 실행 방법
- `.env.example`
- OpenAPI schema
- Alembic migration
- seed data
- ERD 또는 데이터 모델 문서
- API fixture
- integration test
- ADR 문서
- known issues

## 19. 완료 보고 형식

백엔드 작업을 완료하면 다음 형식으로 보고한다.

```text
## 완료한 작업
- ...

## 변경된 API
- METHOD /path: 설명

## 변경된 DB 모델/마이그레이션
- ...

## 프론트엔드 영향
- ...

## 테스트
- ...

## 남은 리스크
- ...
```
