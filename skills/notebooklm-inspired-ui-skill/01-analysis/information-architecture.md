# Information Architecture

## 1. 역할

### Context

입력 범위와 탐색 구조를 관리한다.

- 파일·데이터·프로젝트·필터·자산·참조 문서

### Work

제품 핵심 작업이 이루어진다.

- 대화·편집·분석·캔버스·비교·작성·실행

### Output

결과를 생성하고 관리한다.

- 보고서·노트·실행 결과·생성 파일·시각화·기록

### Evidence / Detail

원문·상세·속성·편집기를 표시한다.

## 2. 객체 모델

```ts
interface Workspace {
  id: string;
  title: string;
  contextItems: ContextItem[];
  sessions: WorkSession[];
  outputs: OutputArtifact[];
}

interface ContextItem {
  id: string;
  type: string;
  title: string;
  selected: boolean;
  status: 'ready' | 'processing' | 'failed' | 'unavailable';
}

interface WorkSession {
  id: string;
  createdAt: string;
  updatedAt: string;
  state: Record<string, unknown>;
}

interface OutputArtifact {
  id: string;
  type: string;
  title: string;
  status: 'draft' | 'generating' | 'ready' | 'failed';
  createdAt: string;
  updatedAt: string;
  contextItemIds: string[];
}
```

## 3. 계층

```text
Product
└─ Workspace Collection
   └─ Workspace
      ├─ Context
      ├─ Work Session
      ├─ Outputs
      └─ Settings
```

Workspace 내부 역할은 별도 페이지라기보다 한 작업 환경의 부분으로 취급한다.

## 4. 화면 상태

### Empty

컨텍스트 없음, 하나의 시작 행동, 지원 입력 안내.

### Ready

선택 가능한 컨텍스트, 요약, 추천 행동, 핵심 실행 UI.

### Active

작업 기록, 생성 상태, 결과 행동, 컨텍스트 변경.

### Detail Review

Evidence 또는 Output 상세를 열되 핵심 작업 상태 유지.

## 5. URL 예시

```text
/workspaces
/workspaces/:workspaceId
/workspaces/:workspaceId/context/:contextId
/workspaces/:workspaceId/outputs/:outputId
/workspaces/:workspaceId/settings
```

Desktop에서는 상세 route를 패널로, Mobile에서는 전체 화면으로 표현할 수 있다.

## 6. URL 상태와 UI 상태

URL:

- Workspace
- 공유 가능한 상세 객체
- 새로고침 후 복구할 객체

로컬 UI:

- 패널 접힘과 너비
- Popover
- hover
- 임시 정렬
- 입력 초안

## 7. 연속성

화면 전환 후 유지할 상태:

- 입력 초안
- 선택 컨텍스트
- 실행 상태
- 열린 결과물
- 패널 스크롤 위치
- 편집 초안

## 8. 권한

```ts
type Permission = 'view' | 'comment' | 'edit' | 'manage';
```

행동을 숨기기만 하지 말고 readonly 상태와 설명을 제공한다.
