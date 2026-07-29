# React Architecture

## 디렉터리

```text
src/
├─ app/
│  ├─ App.tsx
│  ├─ routes/
│  ├─ providers/
│  └─ layouts/
├─ pages/
├─ features/
│  ├─ context/
│  ├─ work/
│  ├─ outputs/
│  ├─ evidence/
│  └─ workspace-settings/
├─ entities/
│  ├─ workspace/
│  ├─ context-item/
│  ├─ work-session/
│  └─ output-artifact/
└─ shared/
   ├─ ui/
   ├─ styles/
   ├─ hooks/
   ├─ utils/
   └─ types/
```

## 책임

### Page

- route params
- page loading
- feature composition
- error boundary

### Feature

- 사용자 행동
- 도메인 orchestration
- mutation
- feature state

### Entity

- 모델
- API adapter
- entity presentation

### Shared UI

- domain store 참조 금지
- 시각·접근성 책임
- props 기반

## Container / Presentation

```tsx
function ContextPanelContainer() {
  const query = useContextItemsQuery();
  const selectedIds = useWorkspaceUIStore(
    (state) => state.selectedContextIds,
  );

  return (
    <ContextPanel
      items={query.data ?? []}
      selectedIds={selectedIds}
      loading={query.isLoading}
    />
  );
}
```

Presentation 컴포넌트는 API 요청을 직접 수행하지 않는다.

## State 분류

Server:

- Workspace
- Context items
- Messages
- Outputs
- Background jobs

Client UI:

- panel mode/width
- selected IDs
- active detail
- draft
- preference

URL:

- workspace ID
- output/context ID
- 공유 가능한 filter

## Error Boundary

패널 단위 Error Boundary를 고려한다. Output Panel 실패가 Core Workspace까지 중단시키지 않게 한다.

## Suspense

전체 화면 하나보다 패널 단위 fallback을 사용한다. refresh 시 기존 데이터를 유지한다.

## Lazy Loading

- PDF Viewer
- Rich Text Editor
- Chart
- Audio/Video Player
- Large output renderer
