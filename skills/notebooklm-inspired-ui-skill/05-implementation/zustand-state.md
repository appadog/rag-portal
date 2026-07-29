# Zustand State

## UI Store

```ts
interface WorkspaceUIState {
  contextMode: 'hidden' | 'rail' | 'default' | 'expanded';
  outputMode: 'hidden' | 'rail' | 'default' | 'expanded';
  contextWidth: number;
  outputWidth: number;

  selectedContextIds: string[];
  activeContextId: string | null;
  activeOutputId: string | null;
  composerDraft: string;

  setContextMode: (mode: WorkspaceUIState['contextMode']) => void;
  setOutputMode: (mode: WorkspaceUIState['outputMode']) => void;
  setContextWidth: (width: number) => void;
  setOutputWidth: (width: number) => void;
  setSelectedContextIds: (ids: string[]) => void;
  setActiveContextId: (id: string | null) => void;
  setActiveOutputId: (id: string | null) => void;
  setComposerDraft: (value: string) => void;
}
```

## Slice

- layoutSlice
- selectionSlice
- detailSlice
- draftSlice
- preferenceSlice

## Selector

```ts
const contextMode = useWorkspaceUIStore(
  (state) => state.contextMode,
);
```

전체 store를 구독하지 않는다.

## Persist

적합:

- panel widths
- density
- theme
- output language
- composer draft 선택

부적합:

- 서버 객체 전체
- 권한
- background job 결과
- 민감 응답
- 임시 오류

## 중복 금지

Query Cache:

- context items
- output list
- messages
- job status

Zustand:

- ID
- layout
- 선택
- 초안
