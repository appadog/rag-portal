# styled-components

## Theme

```ts
export const theme = {
  colors: lightColors,
  spacing,
  radius,
  typography,
  shadow,
  motion,
  zIndex,
  layout,
};

export type AppTheme = typeof theme;
```

```ts
import 'styled-components';
import type { AppTheme } from './theme';

declare module 'styled-components' {
  export interface DefaultTheme extends AppTheme {}
}
```

## Global Style

```ts
import { createGlobalStyle } from 'styled-components';

export const GlobalStyle = createGlobalStyle`
  *,
  *::before,
  *::after {
    box-sizing: border-box;
  }

  html,
  body,
  #root {
    width: 100%;
    height: 100%;
  }

  body {
    margin: 0;
    overflow: hidden;
    color: ${({ theme }) => theme.colors.textPrimary};
    background: ${({ theme }) => theme.colors.canvas};
    font-family: ${({ theme }) => theme.typography.fontFamily};
  }

  button,
  input,
  textarea,
  select {
    font: inherit;
  }

  @media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
      scroll-behavior: auto !important;
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
    }
  }
`;
```

## Transient Props

```ts
interface PanelRootProps {
  $mode: 'rail' | 'default' | 'expanded';
  $width: number;
}
```

style prop에는 `$` prefix를 사용한다.

## Variant

나쁜 예:

```tsx
<Card blue rounded elevated active compact />
```

좋은 예:

```tsx
<Card variant="interactive" state="selected" density="compact" />
```

## Workspace

```tsx
const WorkspaceGrid = styled.main`
  display: grid;
  grid-template-columns:
    minmax(
      ${({ theme }) => theme.layout.contextPanelMin},
      var(--context-width)
    )
    minmax(${({ theme }) => theme.layout.contentMin}, 1fr)
    minmax(
      ${({ theme }) => theme.layout.outputPanelMin},
      var(--output-width)
    );
  gap: ${({ theme }) => theme.layout.panelGap};
  min-height: 0;
  padding: 0 ${({ theme }) => theme.layout.appPadding}
    ${({ theme }) => theme.layout.appPadding};
`;

const Panel = styled.section`
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: ${({ theme }) => theme.radius.xl};
  background: ${({ theme }) => theme.colors.surface};
`;
```

## Colocation

```text
Button/
├─ Button.tsx
├─ Button.styles.ts
├─ Button.types.ts
├─ Button.test.tsx
└─ index.ts
```

## CSS Variables

resize처럼 자주 변경되는 값은 CSS variable로 전달한다.

```tsx
<WorkspaceGrid
  style={{
    '--context-width': `${contextWidth}px`,
    '--output-width': `${outputWidth}px`,
  } as React.CSSProperties}
/>
```
