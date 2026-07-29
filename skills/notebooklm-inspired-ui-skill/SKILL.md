---
name: notebooklm-inspired-ui
description: >
  NotebookLM/Gemini Notebook의 정보 중심 멀티패널 UI와
  source-grounded AI 상호작용을 분석해 일반화한 프론트엔드 설계 스킬.
version: 2.0.0
language: ko-KR
status: production-ready
recommended_stack:
  framework: React
  language: TypeScript
  build_tool: Vite
  styling: styled-components
  state_management: Zustand
  server_state: TanStack Query
  icons: lucide-react
---

# NotebookLM-Inspired UI Skill

## 1. 목적

이 스킬은 NotebookLM의 화면을 픽셀 단위로 복제하지 않는다. 다음 설계 원리를 다른 제품에 적용한다.

1. Context → Work → Output 작업 구조
2. 핵심 작업 중심의 유연한 멀티패널 레이아웃
3. 긴 콘텐츠를 읽고 검증하기 좋은 차분한 시각 체계
4. AI 결과의 근거·상태·한계를 확인하는 상호작용
5. 생성 결과물을 관리 가능한 객체로 다루는 방식
6. 데스크톱 병렬 작업과 모바일 단일 작업 집중

## 2. 적용 대상

- AI 리서치·지식 관리·문서 질의응답
- 멀티패널 업무용 워크스페이스
- 입력 데이터와 결과물을 함께 관리하는 생성형 AI 제품
- 사이드바·중앙 작업·상세 패널이 필요한 관리 도구
- 긴 문서·대화·결과물을 동시에 검토하는 제품

일반 SaaS나 비-AI 제품에서는 필요한 원칙만 선택 적용한다.

## 3. 문서 로딩 순서

### 새 제품 전체 설계

1. `01-analysis/ui-analysis.md`
2. `01-analysis/information-architecture.md`
3. `02-foundations/design-principles.md`
4. `02-foundations/design-tokens.md`
5. `03-patterns/workspace-shell.md`
6. `04-components/components.md`
7. `05-implementation/react-architecture.md`
8. `06-adaptation/product-mapping.md`
9. `06-adaptation/review-checklist.md`

### 기존 화면 개선

1. `02-foundations/design-principles.md`
2. `03-patterns/interaction-patterns.md`
3. `04-components/state-matrix.md`
4. `06-adaptation/review-checklist.md`

### React 구현

1. `02-foundations/design-tokens.md`
2. `04-components/component-api.md`
3. `05-implementation/react-architecture.md`
4. `05-implementation/styled-components.md`
5. `05-implementation/zustand-state.md`
6. `05-implementation/accessibility.md`
7. `05-implementation/testing.md`

## 4. 핵심 원칙

### Core Work First

가장 넓고 안정적인 공간은 핵심 작업에 배정한다. 보조 패널과 도구는 핵심 작업과 시각적으로 경쟁하지 않는다.

### Context Is Visible

현재 작업에 영향을 주는 선택 항목·입력 자료·필터·환경을 사용자가 확인할 수 있어야 한다.

### Outputs Are Objects

AI 결과와 분석 결과를 다음 속성을 가진 객체로 설계한다.

- 타입
- 제목
- 상태
- 생성·수정 시각
- 사용 컨텍스트
- 열기·편집·복제·내보내기·재생성·삭제

### Verification Is First-Class

근거 검증이 필요한 제품에서는 결과에서 원문 위치로 이동하는 흐름을 핵심 사용자 흐름으로 취급한다.

### Progressive Density

빈 상태는 단순하게, 작업이 깊어질수록 정보 밀도를 높인다.

### Stable Geometry

로딩·스트리밍·패널 전환 중 화면 구조가 불필요하게 흔들리지 않게 한다.

## 5. 기본 화면 모델

```text
┌──────────────────────────────────────────────────────────────┐
│ Global Header                                                │
├───────────────┬──────────────────────────────┬───────────────┤
│ Context       │ Core Workspace               │ Output/Detail │
│ Panel         │                              │ Panel         │
└───────────────┴──────────────────────────────┴───────────────┘
```

| NotebookLM 역할 | 일반 역할 | 예시 |
|---|---|---|
| Sources | Context / Inputs / Navigation | 데이터셋, 파일, 자산 |
| Chat | Core Workspace | 편집기, 분석, 캔버스, 대화 |
| Studio | Output / Detail | 결과물, 속성, 실행 기록 |
| Source Viewer | Evidence / Preview | 원문, 상세, 미리보기 |
| Note Editor | Editable Artifact | 보고서, 문서, 결과 편집기 |

3패널은 참조 모델이며 필수 구조가 아니다.

## 6. 구현 전 질문

1. 사용자의 핵심 작업은 무엇인가?
2. 핵심 작업에 영향을 주는 컨텍스트는 무엇인가?
3. 결과물은 저장·재사용되는가?
4. 입력과 결과를 동시에 봐야 하는가?
5. 원문 추적이 필요한가?
6. 보조 패널은 항상 보여야 하는가?
7. 모바일에서 우선할 단일 작업은 무엇인가?
8. 생성 작업이 화면 이동 후에도 유지되어야 하는가?
9. 서버 작업 상태를 복구할 식별자가 있는가?
10. 기존 디자인 시스템과 충돌하는 규칙은 무엇인가?

## 7. 생성 절차

1. 도메인 용어와 핵심 사용자 흐름을 확인한다.
2. 화면 요소를 Context / Work / Output 역할로 분류한다.
3. 핵심 영역의 최소 너비와 읽기 폭을 정한다.
4. 보조 패널의 표시·축소·확장 방식을 정한다.
5. 주요 컴포넌트의 상태 행렬을 작성한다.
6. 로딩·빈 상태·오류·권한 부족·데이터 부족을 구현한다.
7. 모바일 전환 모델을 정의한다.
8. 디자인 토큰만 사용한다.
9. 키보드와 스크린 리더 흐름을 검증한다.
10. Definition of Done으로 완료 여부를 판단한다.

## 8. 금지 사항

- 로고·고유 일러스트·문구를 그대로 복제하지 않는다.
- 모든 화면을 강제로 3패널로 만들지 않는다.
- 모든 콘텐츠를 카드로 감싸지 않는다.
- 가짜 진행률을 표시하지 않는다.
- AI 결과를 항상 정확한 정보처럼 표현하지 않는다.
- 중요한 기능을 hover에만 숨기지 않는다.
- 모바일에서 데스크톱 구조를 단순 축소하지 않는다.
- 서버 상태를 Zustand에 중복 저장하지 않는다.
- 색상·간격·radius를 하드코딩하지 않는다.
- boolean 스타일 prop을 무분별하게 추가하지 않는다.

## 9. 결과물 요구사항

- 역할별 정보 구조
- 데스크톱·태블릿·모바일 레이아웃
- 디자인 토큰
- 공통 컴포넌트 상태
- 빈 상태·로딩·오류 처리
- 접근성 속성
- 패널 및 스크롤 정책
- AI 기능의 생성·중단·재시도 상태
- 제품별 적용 근거
- 완료 체크 결과

## 10. Definition of Done

- [ ] 핵심 작업이 가장 명확한 영역에 있다.
- [ ] 현재 컨텍스트를 확인할 수 있다.
- [ ] 보조 패널이 핵심 작업을 침범하지 않는다.
- [ ] 각 패널의 스크롤 소유권이 명확하다.
- [ ] 모든 인터랙티브 요소에 상태가 정의되어 있다.
- [ ] 로딩 중 기존 콘텐츠가 불필요하게 사라지지 않는다.
- [ ] 모바일에서 단일 작업 흐름으로 전환된다.
- [ ] 키보드만으로 핵심 흐름을 완료할 수 있다.
- [ ] 아이콘 버튼에 접근 가능한 이름이 있다.
- [ ] AI 결과의 상태와 한계가 명확하다.
- [ ] 결과물 객체의 생성·열기·관리 흐름이 있다.
- [ ] 기존 디자인 시스템과 충돌하지 않는다.
