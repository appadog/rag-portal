import { createGlobalStyle } from 'styled-components';

export const theme = {
  colors: {
    canvas: 'var(--rp-canvas)',
    surface: 'var(--rp-surface)',
    surfaceMuted: 'var(--rp-surface-subtle)',
    ink: 'var(--rp-ink)',
    muted: 'var(--rp-ink-muted)',
    line: 'var(--rp-border)',
    brand: 'var(--rp-action)',
    brandHover: 'var(--rp-action-hover)',
    brandSoft: 'var(--rp-surface-selected)',
    accent: 'var(--rp-accent)',
    accentSoft: 'var(--rp-surface-selected)',
    danger: 'var(--rp-status-danger)',
    dangerSoft: 'var(--rp-surface-danger)',
    success: 'var(--rp-status-success)',
    successSoft: 'var(--rp-surface-success)',
    progress: 'var(--rp-status-progress)',
    progressSoft: 'var(--rp-surface-info)',
    warning: 'var(--rp-status-warning)',
    warningSoft: 'var(--rp-surface-warning)',
  },
  radius: {
    sm: 'var(--rp-radius-sm)',
    md: 'var(--rp-radius-md)',
    lg: 'var(--rp-radius-lg)',
    pill: '999px',
  },
  shadow: 'var(--rp-shadow-card)',
};

export const GlobalStyle = createGlobalStyle`
  * { box-sizing: border-box; }
  html, body, #root { width: 100%; height: 100%; overflow: hidden; }
  html { background: ${theme.colors.canvas}; }
  body { margin: 0; min-width: 0; color: ${theme.colors.ink}; font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif; -webkit-font-smoothing: antialiased; }
  button, input, select, textarea { font: inherit; }
  button { cursor: pointer; }
  button:disabled { cursor: not-allowed; }
  a { color: inherit; text-decoration: none; }
  :focus-visible { outline: 0; box-shadow: var(--rp-focus-ring); }
  ::selection { background: ${theme.colors.brandSoft}; }
  @media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition-duration: 0ms !important; animation-duration: 0ms !important; } }
`;
