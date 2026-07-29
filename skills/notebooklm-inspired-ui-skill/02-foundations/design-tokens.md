# Design Tokens

아래 값은 공개 UI 관찰을 일반화한 권장값이며 공식 Google 토큰이 아니다.

## 원칙

- 값이 아니라 역할 이름을 사용한다.
- 컴포넌트에서 hex와 px를 직접 작성하지 않는다.
- semantic token이 primitive token을 참조한다.
- light/dark에서 semantic role을 유지한다.
- 기존 디자인 시스템이 있으면 역할을 매핑한다.

## TypeScript

```ts
export const primitiveColors = {
  neutral: {
    0: '#FFFFFF',
    50: '#F7F7FA',
    100: '#F1F2F6',
    200: '#E4E6ED',
    300: '#D4D7E0',
    400: '#A9ADB8',
    500: '#7B808B',
    600: '#5B606A',
    700: '#3F434B',
    800: '#292C32',
    900: '#1C1E22',
  },
  indigo: {
    50: '#F0F2FF',
    100: '#E4E8FF',
    300: '#A7B2FF',
    500: '#5367F5',
    600: '#4557DC',
    700: '#3847B8',
  },
  red: {
    50: '#FFF0EF',
    500: '#D94A43',
    700: '#A8322D',
  },
  green: {
    50: '#EAF7EF',
    500: '#248A50',
    700: '#176A3B',
  },
  amber: {
    50: '#FFF7E3',
    500: '#B7791F',
    700: '#8A570F',
  },
  blue: {
    50: '#EDF5FF',
    500: '#3276C9',
    700: '#245896',
  },
} as const;

export const lightColors = {
  canvas: '#F3F3FB',
  surface: primitiveColors.neutral[0],
  surfaceSubtle: primitiveColors.neutral[50],
  surfaceHover: primitiveColors.neutral[100],
  surfaceSelected: primitiveColors.indigo[50],
  surfaceElevated: primitiveColors.neutral[0],

  textPrimary: primitiveColors.neutral[900],
  textSecondary: primitiveColors.neutral[600],
  textTertiary: primitiveColors.neutral[500],
  textDisabled: primitiveColors.neutral[400],
  textInverse: primitiveColors.neutral[0],

  borderSubtle: primitiveColors.neutral[200],
  borderDefault: primitiveColors.neutral[300],
  borderStrong: primitiveColors.neutral[400],
  borderFocus: primitiveColors.indigo[500],

  actionPrimary: primitiveColors.indigo[500],
  actionPrimaryHover: primitiveColors.indigo[600],
  actionPrimaryActive: primitiveColors.indigo[700],
  actionPrimarySoft: primitiveColors.indigo[50],

  success: primitiveColors.green[700],
  successSoft: primitiveColors.green[50],
  warning: primitiveColors.amber[700],
  warningSoft: primitiveColors.amber[50],
  danger: primitiveColors.red[700],
  dangerSoft: primitiveColors.red[50],
  info: primitiveColors.blue[700],
  infoSoft: primitiveColors.blue[50],
} as const;

export const spacing = {
  0: '0',
  1: '4px',
  2: '8px',
  3: '12px',
  4: '16px',
  5: '20px',
  6: '24px',
  8: '32px',
  10: '40px',
  12: '48px',
  16: '64px',
} as const;

export const radius = {
  xs: '4px',
  sm: '6px',
  md: '10px',
  lg: '14px',
  xl: '18px',
  pill: '9999px',
} as const;

export const typography = {
  fontFamily:
    'Inter, Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  display: {
    fontSize: '32px',
    lineHeight: '40px',
    fontWeight: 600,
    letterSpacing: '-0.02em',
  },
  titleLarge: {
    fontSize: '24px',
    lineHeight: '32px',
    fontWeight: 600,
    letterSpacing: '-0.015em',
  },
  titleMedium: {
    fontSize: '18px',
    lineHeight: '26px',
    fontWeight: 600,
  },
  titleSmall: {
    fontSize: '16px',
    lineHeight: '24px',
    fontWeight: 600,
  },
  bodyLarge: {
    fontSize: '16px',
    lineHeight: '26px',
    fontWeight: 400,
  },
  bodyMedium: {
    fontSize: '14px',
    lineHeight: '22px',
    fontWeight: 400,
  },
  bodySmall: {
    fontSize: '13px',
    lineHeight: '20px',
    fontWeight: 400,
  },
  label: {
    fontSize: '12px',
    lineHeight: '16px',
    fontWeight: 500,
  },
} as const;

export const shadow = {
  panel: '0 1px 2px rgba(20, 24, 35, 0.02)',
  popover:
    '0 8px 24px rgba(20, 24, 35, 0.12), 0 2px 6px rgba(20, 24, 35, 0.06)',
  modal:
    '0 20px 56px rgba(20, 24, 35, 0.18), 0 4px 12px rgba(20, 24, 35, 0.08)',
} as const;

export const motion = {
  duration: {
    instant: '80ms',
    fast: '120ms',
    normal: '180ms',
    slow: '240ms',
  },
  easing: {
    standard: 'cubic-bezier(0.2, 0, 0, 1)',
    emphasized: 'cubic-bezier(0.2, 0.8, 0.2, 1)',
    exit: 'cubic-bezier(0.4, 0, 1, 1)',
  },
} as const;

export const zIndex = {
  base: 0,
  sticky: 10,
  dropdown: 100,
  drawer: 200,
  modal: 300,
  toast: 400,
} as const;

export const layout = {
  globalHeaderHeight: '56px',
  panelHeaderHeight: '56px',
  appPadding: '16px',
  panelGap: '16px',
  contextPanelMin: '240px',
  contextPanelDefault: '300px',
  contextPanelMax: '420px',
  outputPanelMin: '280px',
  outputPanelDefault: '340px',
  outputPanelMax: '480px',
  contentMin: '520px',
  readingWidth: '720px',
  railWidth: '64px',
  composerMaxHeight: '240px',
} as const;
```

## Dark Theme

```ts
export const darkColors = {
  canvas: '#111217',
  surface: '#191B21',
  surfaceSubtle: '#20232A',
  surfaceHover: '#292C34',
  surfaceSelected: '#28304C',
  surfaceElevated: '#24272F',

  textPrimary: '#F1F2F5',
  textSecondary: '#C0C3CB',
  textTertiary: '#969BA6',
  textDisabled: '#676C76',
  textInverse: '#1C1E22',

  borderSubtle: '#2C3038',
  borderDefault: '#3A3E47',
  borderStrong: '#555A65',
  borderFocus: '#9EAAFF',

  actionPrimary: '#8C9AFF',
  actionPrimaryHover: '#A6B0FF',
  actionPrimaryActive: '#BBC3FF',
  actionPrimarySoft: '#272F4C',

  success: '#77D49A',
  successSoft: '#163825',
  warning: '#E9BB65',
  warningSoft: '#3B2D13',
  danger: '#FF9A94',
  dangerSoft: '#47201D',
  info: '#8FC2FF',
  infoSoft: '#19324D',
} as const;
```

## Density

```ts
type Density = 'comfortable' | 'compact';
```

comfortable:

- 목록 행 `48–56px`
- 패널 padding `16px`
- gap `12px`

compact:

- 목록 행 `36–44px`
- 패널 padding `12px`
- gap `8px`
