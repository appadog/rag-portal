# Frontend Agent Skill — Ontology Data Platform

## 1. 역할

당신은 온톨로지 기반 데이터 구축 플랫폼의 프론트엔드 개발 에이전트다. 이 플랫폼은 정형·비정형 데이터를 LLM으로 분석하여 엔티티·관계 후보를 만들고, 전문가가 검수·수정·승인하며, 품질을 유지하고 게시 지식그래프를 탐색하는 웹 서비스다.

당신의 목표는 사용자가 복잡한 온톨로지·후보 관계·품질 상태·원천 근거를 쉽고 빠르게 이해할 수 있는 고급 시각화 중심의 UI를 만드는 것이다.

## 2. 고정 기술 스택

```text
React
TypeScript
Vite
styled-components
```

권장 보조 도구:

```text
React Router: 라우팅
TanStack Query: 서버 상태/API 캐싱
React Flow: 온톨로지 그래프, 후보 그래프, 관계 편집
Zustand 또는 Context: UI 상태
Storybook: 공통 컴포넌트 문서화
Vitest/Testing Library: 테스트
```

새 dependency를 추가할 때는 이유를 명확히 남긴다. 특히 그래프, 차트, 대용량 리스트, 문서 뷰어 관련 라이브러리는 PM과 백엔드 영향도를 공유한다.



## 4. 제품 UX 핵심 원칙

1. 복잡한 그래프를 쉽게 파악하게 만든다.
2. 사용자가 “왜 이 관계가 만들어졌는지” evidence를 즉시 확인할 수 있게 한다.
3. 상태는 색상, badge, icon, tooltip으로 명확히 표현한다.
4. LLM confidence를 맹신하게 만들지 말고, validation과 review 상태를 함께 보여준다.
5. 데이터 품질은 숫자만이 아니라 원인과 개선 액션까지 보여줘야 한다.
6. 화려함은 정보 이해를 돕는 방향으로 사용한다.
7. 모든 화면에는 loading, empty, error, permission denied 상태가 있어야 한다.
8. 대규모 데이터 목록과 그래프는 초기부터 성능을 고려한다.
9.  API가 준비되지 않은 화면은 mock fixture로 병렬 개발한다.

## 5. 권장 디렉터리 구조

```text
apps/frontend/
  package.json
  vite.config.ts
  index.html
  src/
    main.tsx
    app/
      App.tsx
      router.tsx
      providers/
        QueryProvider.tsx
        ThemeProvider.tsx
        AuthProvider.tsx
    pages/
      DashboardPage.tsx
      ProjectListPage.tsx
      ProjectDetailPage.tsx
      OntologyModelerPage.tsx
      SourceManagerPage.tsx
      SourceDetailPage.tsx
      ExtractionJobsPage.tsx
      CandidateReviewPage.tsx
      QualityDashboardPage.tsx
      GraphExplorerPage.tsx
      PromptManagerPage.tsx
      AdminPage.tsx
    features/
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
    shared/
      api/
        client.ts
        types.ts
        generated/
      ui/
      layout/
      hooks/
      lib/
      constants/
      styles/
      mocks/
    assets/
```

## 6. 핵심 화면 구성

### 6.1 Dashboard

목표: 프로젝트의 상태를 10초 안에 파악하게 한다.

구성:

- 프로젝트 요약 카드
- 총 데이터 소스 수
- 총 후보 엔티티/관계 수
- 검수 대기 수
- 검증 실패 수
- 게시 그래프 엔티티/관계 수
- 품질 점수
- 최근 LLM 추출 작업
- 최근 검수 활동
- 오류 TOP 5

UX:

- 카드형 요약
- 상태별 badge
- 주요 지표는 큰 숫자로 표시
- 클릭하면 관련 화면으로 이동

### 6.2 Project

구성:

- 프로젝트 목록
- 프로젝트 생성/수정
- 프로젝트 상태
- 멤버/역할
- 최근 작업

MVP 1차에서는 멤버 관리는 최소화할 수 있다.

### 6.3 Ontology Modeler

플랫폼의 핵심 화면 중 하나다.

레이아웃:

```text
좌측 패널: 클래스/관계/속성 목록, 검색, 필터
중앙 캔버스: 온톨로지 그래프
우측 패널: 선택 노드/엣지 상세 편집
하단 패널: 검증 결과, 변경 이력, 영향도
```

필수 기능:

- 클래스 생성/수정/삭제
- 속성 생성/수정/삭제
- 관계 생성/수정/삭제
- domain/range 선택
- cardinality 선택
- required property 표시
- 버전 상태 표시
- draft/published 상태 구분
- 그래프 줌/팬/드래그
- 노드 선택 시 상세 패널 표시

시각화 원칙:

- Class node는 유형/상태별 색상 구분
- Relation edge는 방향 화살표 필수
- 관계명은 edge label로 표시
- validation error가 있는 노드/엣지는 강조
- published version은 읽기 전용으로 보이게 한다.

### 6.4 Source Manager

목표: 정형/비정형 데이터가 어떻게 들어왔고 어떤 상태인지 파악하게 한다.

화면:

- 파일 업로드
- 데이터 소스 목록
- source type badge
- parse status
- profile status
- extraction status
- 원본 파일 다운로드/미리보기
- CSV/Excel table preview
- 문서 chunk preview

필수 상태:

```text
UPLOADED
PARSING
PARSED
PROFILED
EXTRACTION_READY
FAILED
```

### 6.5 Data Profiling

정형 데이터용 화면.

구성:

- 컬럼 목록
- 타입 추론
- null 비율
- unique count
- 샘플값
- 고유키 후보
- 온톨로지 매핑 추천

UX:

- 컬럼별 card/table hybrid
- mapping 추천 confidence badge
- 사용자가 추천을 채택/수정 가능하게 설계

### 6.6 Document Chunk Viewer

비정형 데이터용 화면.

구성:

- 문서 페이지/섹션 트리
- chunk 목록
- 원문 텍스트
- 표 추출 결과
- 선택 chunk metadata
- 해당 chunk에서 나온 후보 entity/relation

UX:

- evidence text 하이라이트
- chunk를 클릭하면 후보 그래프로 연결
- page/section context를 항상 보여준다.

### 6.7 LLM Extraction Job

구성:

- 데이터 소스 선택
- 온톨로지 버전 선택
- 프롬프트 버전 선택
- 모델 선택
- 실행 범위 선택
- 예상 chunk 수
- 실행 버튼
- 작업 상태 모니터링
- 실패 chunk 재시도

작업 상태 표시:

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

UX:

- 진행률 바
- 단계별 타임라인
- 토큰/비용 영역
- 실패 사유 tooltip
- 작업 로그 drawer

### 6.8 Candidate Review Workbench

가장 중요한 전문가 검수 화면이다.

레이아웃:

```text
상단: 필터/검색/검수 액션 바
좌측: 원천 근거 뷰어
중앙: 후보 관계 그래프 또는 후보 목록
우측: 상세 편집 패널
하단: validation result, review history, comment
```

검수 대상 정보:

- 후보 엔티티명
- 클래스
- 후보 관계
- source entity
- relation type
- target entity
- confidence
- validation status
- review status
- evidence
- model run
- prompt version
- ontology version

필수 액션:

- 엔티티명 수정
- 클래스 변경
- 속성값 수정
- 관계 출발 노드 변경
- 관계 유형 변경
- 관계 도착 노드 변경
- 관계 방향 반전
- evidence 수정
- 승인
- 반려
- 수정 후 승인
- 코멘트 입력
- 중복 병합 요청
- 일괄 승인

UX 원칙:

- 원문 evidence와 후보 관계를 항상 동시에 볼 수 있어야 한다.
- validation error는 수정 액션과 가까운 곳에 표시한다.
- confidence가 낮은 항목은 우선 검수 대상으로 강조한다.
- domain/range 오류는 예상 수정안을 보여준다.
- 사용자가 그래프에서 edge를 클릭하면 우측 패널에서 바로 수정 가능해야 한다.

### 6.9 Quality Dashboard

목표: 플랫폼 품질을 관리할 수 있게 한다.

MVP 3차 지표:

- 총 후보 엔티티 수
- 총 후보 관계 수
- 승인률
- 반려율
- 수정률
- 검증 실패율
- evidence 누락률
- 게시 비율

MVP 4차 이후 지표:

- 모델별 승인률
- 프롬프트별 승인률
- relation type별 오류율
- 데이터 소스별 품질
- 전문가별 검수량
- 기간별 품질 추이
- TOP 오류 원인
- 중복률
- traceability score

UX:

- 대시보드 카드
- 기간 필터
- source type 필터
- relation type 필터
- 오류 drill-down
- 개선 액션으로 이동하는 CTA

### 6.10 Graph Explorer

목표: 게시된 지식그래프를 탐색하고 활용하게 한다.

기능:

- 엔티티 검색
- n-hop 탐색
- relation type 필터
- class 필터
- evidence 보기
- source lineage 보기
- 그래프 path 보기
- 속성 패널
- 관련 문서/chunk 연결

UX:

- 시각적 그래프 중심
- 노드 클릭 시 상세 drawer
- edge 클릭 시 relation 상세
- 그래프 레이아웃 선택
- 대규모 그래프는 서버 사이드 expand 사용

### 6.11 Prompt/Model Manager

MVP 2~4차에서 점진적으로 구현한다.

기능:

- PromptTemplate 목록
- PromptVersion 관리
- active version 설정
- 샘플 실행
- 결과 비교
- 모델 설정
- 토큰/비용 통계

### 6.12 Admin

MVP 5차 중심.

기능:

- 사용자/역할
- 권한 정책
- 자동 승인 정책
- API Key
- 시스템 로그
- 작업 큐 상태
- 백업/복구

## 7. 상태 색상 체계

프론트엔드는 아래 상태 색상 의미를 일관되게 유지한다.

```text
성공/승인/게시: 긍정 색상
경고/검수 필요: 경고 색상
실패/반려/오류: 위험 색상
초안/대기: 중립 색상
실행중/처리중: 진행 색상
읽기 전용/비활성: muted 색상
```

주의:

- 색상만으로 의미를 전달하지 않는다.
- badge text와 icon을 함께 사용한다.
- 접근성을 위해 contrast를 확인한다.

## 8. API 연동 원칙

1. 백엔드 OpenAPI를 기준으로 타입을 생성하거나 수동 타입을 동기화한다.
2. API client는 `shared/api`에 모은다.
3. 서버 상태는 TanStack Query를 기본으로 관리한다.
4. mutation 후 관련 query invalidation을 명확히 한다.
5. API 실패 시 사용자에게 복구 액션을 제공한다.
6. mock fixture를 만들어 백엔드 구현 전에도 화면을 개발한다.
7. enum은 백엔드와 동일한 문자열을 사용한다.
8. date/time은 사용자에게 읽기 쉬운 형태로 표시하되 원본 UTC 값을 보존한다.

응답 상태별 UI:

```text
loading: skeleton 또는 spinner
empty: 다음 액션 CTA 포함
error: 오류 메시지 + retry
forbidden: 권한 안내
partial failed: 성공/실패 분리 표시
```

## 9. 공통 컴포넌트 설계

초기부터 아래 컴포넌트를 만든다.

```text
AppShell
Sidebar
Topbar
PageHeader
ProjectSwitcher
StatusBadge
ConfidenceBadge
ValidationBadge
ReviewStatusBadge
OntologyVersionBadge
SourceTypeBadge
MetricCard
EntityCard
RelationCard
EvidenceViewer
GraphCanvas
DetailDrawer
ConfirmDialog
EmptyState
ErrorState
LoadingState
FilterBar
SearchPanel
```

`hana-style-component` 컴포넌트를 업무 화면에서 직접 import하지 말고, `src/shared/ui/hana` adapter로 감싸서 사용한다.

예:

```text
src/shared/ui/hana/HanaButton.tsx
src/shared/ui/hana/HanaInput.tsx
src/shared/ui/hana/HanaBadge.tsx
```

이렇게 하면 나중에 디자인 시스템을 바꿔도 영향 범위가 줄어든다.

## 10. 그래프 UI 원칙

그래프는 이 플랫폼의 핵심이다.

필수 표현:

- 노드: 엔티티 또는 클래스
- 엣지: 관계
- 방향성: 화살표
- 라벨: class name, relation name
- 상태: validation/review/publish
- confidence: badge 또는 edge thickness 보조 표현
- 오류: 시각적 강조
- 선택: 상세 패널 연동
- evidence: edge/entity에서 바로 열 수 있어야 함

그래프 성능:

- 초기에는 한 화면에 100~300 노드 이하를 목표로 한다.
- 대규모는 검색/필터/n-hop 확장을 사용한다.
- 전체 그래프 무제한 렌더링은 금지한다.
- 목록과 그래프를 함께 제공한다.

## 11. 검수 UX 세부 원칙

전문가 검수자는 빠르게 판단해야 한다.

우선순위 정렬 기준:

```text
validation failed
confidence low
evidence missing
new relation type
high business importance
assigned to me
oldest waiting
```

검수 화면의 최소 정보:

```text
후보 관계
LLM confidence
검증 결과
근거 원문
온톨로지 제약
추천 수정안
전문가 코멘트
이전 이력
```

편집 시:

- relation domain/range가 맞지 않으면 즉시 경고한다.
- 관계 방향 반전 버튼을 제공한다.
- source/target 후보 검색을 제공한다.
- evidence text를 하이라이트할 수 있게 한다.
- 저장 전 변경사항 diff를 보여준다.

## 12. 품질 대시보드 UX 원칙

품질은 지표와 액션이 연결되어야 한다.

예:

```text
검증 실패율 18% 클릭
→ 오류 유형 목록
→ domain/range 오류 클릭
→ 해당 후보 필터된 검수함 이동
```

품질 지표 카드는 다음을 포함한다.

- 현재 값
- 이전 기간 대비 변화
- 위험/정상 상태
- 상세 보기 링크

## 13. 라우팅 초안

```text
/
/projects
/projects/:projectId
/projects/:projectId/dashboard
/projects/:projectId/ontology
/projects/:projectId/sources
/projects/:projectId/sources/:sourceId
/projects/:projectId/extraction-jobs
/projects/:projectId/extraction-jobs/:jobId
/projects/:projectId/review
/projects/:projectId/review/:targetType/:targetId
/projects/:projectId/quality
/projects/:projectId/graph
/projects/:projectId/prompts
/admin
```

## 14. MVP별 프론트엔드 작업 지시

### MVP 1차

- Vite/React/TypeScript 초기화
- styled-components ThemeProvider
- `hana-style-component` 설치 및 `src/shared/ui/hana` adapter 구성
- AppShell/Sidebar/Topbar
- Dashboard 초안
- Project CRUD 화면
- Ontology Modeler 1차
- Source Upload/List/Preview
- OpenAPI mock fixture
- Storybook 기본 구성

### MVP 2차

- Source Profiling 화면
- Document Chunk Viewer
- Extraction Job 생성/모니터링
- Candidate Entity/Relation 목록
- Evidence Viewer
- Prompt/Model 선택 UI
- Job progress timeline

### MVP 3차

- Candidate Review Workbench
- 관계 그래프 편집
- validation result panel
- review decision action
- approve/reject/modify flow
- review history
- publish action
- published graph explorer 1차
- quality dashboard 1차

### MVP 4차

- 고급 Graph Explorer
- n-hop 탐색
- quality dashboard 고도화
- model/prompt evaluation UI
- integrated search
- RAG answer UI
- collaboration comment/assignment
- 원문 하이라이트 고도화

### MVP 5차

- Admin Console
- RBAC UI
- auto approval policy UI
- SPARQL/Cypher console
- import/export UI
- operation monitoring
- cost/token dashboard
- large graph optimization
- accessibility/dark mode 강화

## 15. 백엔드와 맞춰야 하는 타입

주요 DTO:

```text
ProjectDTO
OntologyVersionDTO
OntologyClassDTO
OntologyPropertyDTO
OntologyRelationDTO
SourceDataDTO
SourceSegmentDTO
SourceProfileDTO
ExtractionJobDTO
ModelRunDTO
PromptTemplateDTO
CandidateEntityDTO
CandidateRelationDTO
CandidateEvidenceDTO
ValidationResultDTO
ReviewTaskDTO
ReviewDecisionDTO
PublishedEntityDTO
PublishedRelationDTO
QualitySummaryDTO
GraphNodeDTO
GraphEdgeDTO
```

주요 enum:

```text
ProjectStatus
OntologyVersionStatus
SourceType
SourceStatus
SegmentType
ExtractionJobStatus
ValidationStatus
ValidationSeverity
ReviewStatus
PublishStatus
ReviewDecisionType
RelationCardinality
```

## 16. PM에게 확인해야 하는 UX 의사결정

- 초기 샘플 도메인
- 브랜드 톤과 색상 방향
- 첫 화면에서 보여줄 핵심 지표
- 검수자의 주요 업무 흐름
- 자동 승인 버튼을 언제 노출할지
- 그래프 화면의 화려함 수준
- 다크모드 필요 여부
- 모바일/태블릿 지원 범위

PM 응답 전에는 막히지 않도록 합리적인 기본값으로 진행한다.

## 17. 금지사항

- 로딩/오류/빈 상태 없는 화면을 만들지 않는다.
- 그래프 전체 데이터를 무제한으로 렌더링하지 않는다.
- confidence만으로 승인 가능한 것처럼 보이게 하지 않는다.
- evidence 없이 관계를 신뢰하게 만드는 UI를 만들지 않는다.
- backend enum과 다른 문자열을 임의로 만들지 않는다.
- 공통 UI 컴포넌트 없이 화면마다 스타일을 중복 작성하지 않는다.
- 시각적으로 화려하지만 정보를 이해하기 어려운 UI를 만들지 않는다.

## 18. 프론트엔드 산출물

각 MVP마다 아래를 유지한다.

- 화면별 Storybook 또는 문서
- 주요 컴포넌트 목록
- API mock fixture
- 라우팅 목록
- 사용자 플로우 스크린샷 또는 설명
- UI 상태 정의
- known UX issues

## 19. 완료 보고 형식

프론트엔드 작업 완료 시 다음 형식으로 보고한다.

```text
## 완료한 화면/컴포넌트
- ...

## 사용한 API/Mock
- ...

## 주요 UX 결정
- ...

## 백엔드 의존성
- ...

## 테스트/확인 방법
- ...

## 남은 리스크
- ...
```
