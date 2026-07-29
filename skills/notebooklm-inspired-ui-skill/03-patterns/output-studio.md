# Output Studio Pattern

## 역할

결과물 타입 선택과 생성 결과 관리를 담당한다.

## 구조

```text
Panel Header
Output Type Tiles
Generated Output List
Background Task Status
```

## Output Type

```ts
interface OutputTypeDefinition {
  type: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  supportsCustomization: boolean;
}
```

Tile에는 타입·설명·Create·Customize를 제공한다. 전체 클릭과 내부 버튼 역할을 충돌시키지 않는다.

## Artifact

```ts
interface OutputArtifact {
  id: string;
  type: string;
  title: string;
  status: 'queued' | 'generating' | 'ready' | 'failed';
  createdAt: string;
  updatedAt: string;
  contextIds: string[];
  progress?: number;
}
```

## 생성 상태

타입·제목·시작 시각·컨텍스트·중단 가능 여부를 유지한다. 전체 카드를 Skeleton로 교체하지 않는다.

## 결과 목록 행동

- Open
- Rename
- Duplicate
- Export
- Regenerate
- Delete

## Multiple Outputs

같은 타입의 결과를 여러 개 만들 수 있게 한다.

```text
Audio Overview
├─ Executive Summary
├─ Korean Study Version
└─ Chapter 3 Review
```

## Multitasking

장기 작업 중에도 다른 결과와 Core Workspace를 사용할 수 있어야 한다. 완료는 조용한 알림, 실패는 명확한 복구 행동으로 전달한다.
