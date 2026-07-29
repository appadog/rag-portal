# Workspace Shell

## 구조

```tsx
<AppShell>
  <GlobalHeader />
  <WorkspaceGrid>
    <ContextPanel />
    <CorePanel />
    <OutputPanel />
  </WorkspaceGrid>
</AppShell>
```

## Grid

```css
grid-template-columns:
  minmax(var(--context-min), var(--context-width))
  minmax(var(--core-min), 1fr)
  minmax(var(--output-min), var(--output-width));
```

## Panel Contract

```tsx
<Panel>
  <PanelHeader />
  <PanelBody />
  <PanelFooter />
</Panel>
```

Footer는 필요할 때만 사용한다. Composer처럼 핵심 행동은 sticky footer가 될 수 있다.

## Panel Header

- 제목
- 카운트 또는 상태
- 검색
- 필터
- 접기/확장
- 더보기

직접 행동은 3개 이내를 권장한다.

## Focus Mode

```text
Context → rail
Core → expanded
Output → hidden 또는 expanded editor
```

## Resize

Desktop에서 선택 적용한다.

- `role="separator"`
- keyboard 조작
- aria min/max/now
- 더블 클릭 기본 너비 복원
- 사용자 설정 저장

## Scroll

```css
html,
body,
#root {
  height: 100%;
}

body {
  overflow: hidden;
}

.panel {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.panel-body {
  min-height: 0;
  overflow: auto;
}
```

## Layout State

```ts
interface WorkspaceLayoutState {
  contextMode: 'hidden' | 'rail' | 'default' | 'expanded';
  outputMode: 'hidden' | 'rail' | 'default' | 'expanded';
  contextWidth: number;
  outputWidth: number;
  activeDetail: null | {
    type: 'context' | 'output';
    id: string;
  };
}
```
