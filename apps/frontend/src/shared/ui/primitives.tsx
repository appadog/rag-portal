import type { ReactNode } from 'react';
import styled, { css } from 'styled-components';
import { theme } from '../styles/theme';
import type { RagStatus } from '../api/types';

export const Button = styled.button<{ $variant?: 'primary' | 'secondary' | 'ghost' | 'danger' }>`
  border: 1px solid transparent;
  border-radius: ${theme.radius.sm};
  min-height: var(--rp-touch-target);
  padding: var(--rp-space-2) var(--rp-space-3);
  font-weight: 700;
  transition: var(--rp-transition-normal);
  white-space: nowrap;
  ${({ $variant = 'primary' }) =>
    $variant === 'primary' &&
    css`
      background: ${theme.colors.brand};
      color: var(--rp-action-on);
      &:hover:not(:disabled) {
        background: ${theme.colors.brandHover};
      }
      &:disabled {
        background: var(--rp-ink-disabled);
      }
    `}
  ${({ $variant }) =>
    $variant === 'secondary' &&
    css`
      background: ${theme.colors.surface};
      border-color: ${theme.colors.line};
      color: ${theme.colors.ink};
      &:hover:not(:disabled) {
        border-color: ${theme.colors.brand};
        color: ${theme.colors.brand};
      }
    `}
  ${({ $variant }) =>
    $variant === 'ghost' &&
    css`
      background: transparent;
      color: ${theme.colors.muted};
      &:hover:not(:disabled) {
        background: ${theme.colors.surfaceMuted};
        color: ${theme.colors.ink};
      }
    `}
  ${({ $variant }) =>
    $variant === 'danger' &&
    css`
      background: ${theme.colors.dangerSoft};
      color: ${theme.colors.danger};
      &:hover:not(:disabled) {
        background: var(--rp-surface-danger);
      }
    `}
`;

export const Card = styled.section`
  background: ${theme.colors.surface};
  border: 1px solid ${theme.colors.line};
  border-radius: ${theme.radius.md};
  box-shadow: ${theme.shadow};
`;

export const Input = styled.input`
  width: 100%;
  min-height: var(--rp-touch-target);
  padding: var(--rp-space-2) var(--rp-space-3);
  border: 1px solid ${theme.colors.line};
  border-radius: ${theme.radius.sm};
  background: var(--rp-surface);
  color: ${theme.colors.ink};
  outline: none;
  &:focus {
    border-color: ${theme.colors.brand};
    box-shadow: var(--rp-focus-ring);
  }
`;

const statusMap: Record<
  RagStatus,
  { icon: string; label: string; tone: 'ready' | 'process' | 'wait' | 'failed' }
> = {
  READY: { icon: '●', label: '준비 완료', tone: 'ready' },
  PROCESSING: { icon: '◐', label: '처리 중', tone: 'process' },
  TUNING: { icon: '◐', label: '비교 중', tone: 'process' },
  SETTING_UP: { icon: '○', label: '설정 중', tone: 'wait' },
  FAILED: { icon: '×', label: '처리 실패', tone: 'failed' },
};
const Badge = styled.span<{ $tone: string }>`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  width: fit-content;
  border-radius: ${theme.radius.pill};
  padding: 5px 9px;
  font-size: 12px;
  font-weight: 750;
  ${({ $tone }) =>
    $tone === 'ready' &&
    css`
      background: ${theme.colors.successSoft};
      color: ${theme.colors.success};
    `}
  ${({ $tone }) =>
    $tone === 'process' &&
    css`
      background: ${theme.colors.progressSoft};
      color: ${theme.colors.progress};
    `}
  ${({ $tone }) =>
    $tone === 'wait' &&
    css`
      background: ${theme.colors.surfaceMuted};
      color: ${theme.colors.muted};
    `}
  ${({ $tone }) =>
    $tone === 'failed' &&
    css`
      background: ${theme.colors.dangerSoft};
      color: ${theme.colors.danger};
    `}
`;
export function StatusBadge({ status, progress }: { status: RagStatus; progress?: string }) {
  const item = statusMap[status];
  return (
    <Badge $tone={item.tone}>
      {item.icon} {progress ?? item.label}
    </Badge>
  );
}

export const Pill = styled.span<{ $tone?: 'brand' | 'muted' | 'warning' }>`
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: ${theme.radius.pill};
  padding: 4px 8px;
  font-size: 11px;
  font-weight: 700;
  ${({ $tone = 'muted' }) =>
    $tone === 'brand' &&
    css`
      background: ${theme.colors.brandSoft};
      color: ${theme.colors.brand};
    `}
  ${({ $tone = 'muted' }) =>
    $tone === 'warning' &&
    css`
      background: ${theme.colors.warningSoft};
      color: ${theme.colors.warning};
    `}
  ${({ $tone = 'muted' }) =>
    $tone === 'muted' &&
    css`
      background: ${theme.colors.surfaceMuted};
      color: ${theme.colors.muted};
    `}
`;

export function LoadingState({ label = '불러오는 중이에요…' }: { label?: string }) {
  return (
    <div role="status" style={{ padding: 'var(--rp-space-8)', color: theme.colors.muted }}>
      {label}
    </div>
  );
}
export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <Card style={{ padding: 28 }}>
      <strong>불러오지 못했어요.</strong>
      <p style={{ color: theme.colors.muted }}>{message}</p>
      {retry && (
        <Button $variant="secondary" onClick={retry}>
          다시 시도
        </Button>
      )}
    </Card>
  );
}
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <Card style={{ padding: 42, textAlign: 'center' }}>
      <div style={{ fontSize: 26 }}>◇</div>
      <h3>{title}</h3>
      <p style={{ color: theme.colors.muted }}>{description}</p>
      {action}
    </Card>
  );
}
