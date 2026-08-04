import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import styled, { css } from 'styled-components';
import { ragApi, SearchPreflightError } from '../../shared/api/client';
import type {
  ChatAnswer,
  ExecutionPlan,
  ModelServiceStatus,
  PipelineCandidate,
  RagInstanceDetail,
  RagProcessingJob,
  SearchContextSnapshot,
} from '../../shared/api/types';
import {
  Button,
  Card,
  ErrorState,
  Input,
  LoadingState,
  Pill,
  StatusBadge,
} from '../../shared/ui/primitives';
import { theme } from '../../shared/styles/theme';

type PanelName = 'context' | 'output';
type OutputView = 'evidence' | 'settings' | 'documents';
type WorkspaceDialog = 'add' | 'delete' | 'reparse';
type StreamingAnswer = Pick<ChatAnswer, 'text' | 'citations' | 'generation'> & {
  question: string;
  context: SearchContextSnapshot;
  state: 'streaming' | 'interrupted' | 'failed';
};

const sensitivityDescriptions: Record<string, string> = {
  flexible: '유연하게: 표현이 조금 달라도 관련된 내용을 넓게 찾아봐요.',
  balanced: '평이하게: 관련성과 범위의 균형을 맞춰 답을 찾아요.',
  strict: '엄격하게: 문서에 더 직접적으로 적힌 내용만 우선해요.',
};
const sensitivityLabels: Record<string, string> = {
  flexible: '유연하게',
  balanced: '평이하게',
  strict: '엄격하게',
};

function initialPanels(width: number): Record<PanelName, boolean> {
  if (width >= 1380) return { context: true, output: true };
  if (width >= 1024) return { context: true, output: false };
  return { context: false, output: false };
}

function documentIsSearchReady(document?: RagInstanceDetail['documents'][number]) {
  const reparseState = document?.provenance?.reparse?.state;
  return Boolean(document?.pipelineId) && reparseState !== 'QUEUED' && reparseState !== 'PARSING';
}

function preflightConflictCopy(
  error: SearchPreflightError,
  documents: RagInstanceDetail['documents'],
) {
  const names = error.documentIds
    .map((documentId) => documents.find((document) => document.id === documentId)?.name)
    .filter((name): name is string => Boolean(name));
  return names.length ? `${names.join(', ')}: ${error.message}` : error.message;
}

function generationStatusCopy(status?: string) {
  const normalized = status?.toLowerCase();
  if (normalized?.includes('ground') || normalized?.includes('evidence'))
    return '문서 근거를 연결하고 있어요.';
  if (normalized?.includes('generat') || normalized?.includes('answer'))
    return '문서 근거를 바탕으로 답을 정리하고 있어요.';
  return '문서에서 근거를 확인하고 있어요.';
}

function fallbackGenerationCopy(reason?: string, detail?: string) {
  if (detail) return `문서 근거를 바탕으로 발췌한 결과예요 · ${detail}`;
  if (reason === 'INVALID_GROUNDING')
    return '근거를 다시 확인하기 위해 문서 발췌 결과를 보여드려요.';
  if (reason === 'GENERATOR_UNAVAILABLE')
    return '생성 모델 연결을 확인하는 동안 문서 발췌 결과를 보여드려요.';
  return '문서 근거를 바탕으로 발췌한 결과예요.';
}

function runtimeTechniqueLabel(technique: string) {
  const labels: Record<string, string> = {
    embedding: '임베딩',
    reranking: '재정렬',
    grounded_generation: '근거 기반 생성',
    ocr: 'OCR',
  };
  return labels[technique] ?? technique;
}

function retuningQualityCopy(state: 'MEASURED' | 'FALLBACK' | 'MISSING' | 'PENDING') {
  if (state === 'MEASURED') return '실측 확인 상태';
  if (state === 'FALLBACK') return '개발용 fallback 결과라 실측 품질 비교에 사용하지 않아요.';
  if (state === 'PENDING') return '실측 비교 결과를 기다리고 있어요.';
  return '실측 품질 결과가 없어 비교 수치를 표시하지 않아요.';
}

function deduplicationCopy(outcome?: string) {
  if (outcome === 'NEW_SOURCE') return '새 원본으로 등록됨';
  if (outcome === 'DUPLICATE_REUSED') return '같은 원본을 찾아 기존 처리 결과를 재사용함';
  if (outcome === 'DUPLICATE_REPLACED') return '같은 원본의 최신 처리 결과로 교체됨';
  return '중복 처리 결과를 확인할 수 없어요.';
}

function reparseStateCopy(state?: string) {
  if (state === 'QUEUED') return '재파싱 대기 중';
  if (state === 'PARSING') return '원본을 다시 읽는 중';
  if (state === 'SUCCEEDED') return '재파싱 완료';
  if (state === 'FAILED') return '재파싱을 완료하지 못했어요';
  return '현재 원본 기준 처리 상태';
}

function checksumCopy(checksum?: string) {
  if (!checksum) return '확인할 수 없음';
  return checksum.length > 16 ? `${checksum.slice(0, 12)}…${checksum.slice(-4)}` : checksum;
}

function operationalJobCopy(job: RagProcessingJob) {
  const state = (job.operationalState ?? job.state).toUpperCase();
  if (state.includes('DEAD') || state.includes('LETTER')) return '작업이 멈춰 복구 대기 중';
  if (state.includes('RECOVER')) return '복구 준비 중';
  if (state.includes('RETRY') || (job.attempt && job.attempt > 0 && state !== 'SUCCEEDED'))
    return '다시 준비 중';
  if (state === 'CANCELLED') return '사용자 요청으로 중단됨';
  if (state === 'FAILED') return job.canRetry ? '복구할 수 있는 실패' : '작업을 완료하지 못했어요';
  if (state === 'SUCCEEDED') return '준비 완료';
  if (state === 'QUEUED') return '준비 대기 중';
  return '문서를 준비하고 있어요';
}

function operationalJobTone(job: RagProcessingJob): 'brand' | 'warning' | 'muted' {
  const state = (job.operationalState ?? job.state).toUpperCase();
  if (state === 'SUCCEEDED') return 'muted';
  if (state.includes('DEAD') || state === 'FAILED') return 'warning';
  if (state === 'CANCELLED' || state.includes('RECOVER')) return 'warning';
  return 'brand';
}

const DetailPage = styled.div`
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-height: 0;

  @media (max-width: 1380px) {
    display: block;
  }
`;
const Header = styled.header`
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--rp-space-4);
  margin-bottom: var(--rp-space-4);
  h1 {
    margin: 0;
    font-size: var(--rp-font-size-24);
    letter-spacing: -0.02em;
  }
  p {
    margin: var(--rp-space-1) 0 0;
    color: var(--rp-ink-muted);
    font-size: var(--rp-font-size-14);
  }
  .job-summary {
    margin-top: var(--rp-space-2);
    color: var(--rp-ink-subtle);
    font-size: var(--rp-font-size-12);
  }
  .tools {
    display: flex;
    gap: var(--rp-space-2);
  }
  @media (max-width: 720px) {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--rp-space-3);
    .tools {
      width: 100%;
      flex-wrap: wrap;
      justify-content: flex-start;
    }
  }
`;
const Workspace = styled.main`
  width: 100%;
  flex: 1 1 auto;
  display: grid;
  grid-template-columns: minmax(15rem, 18rem) minmax(32rem, 1fr) minmax(17.5rem, 21rem);
  gap: var(--rp-space-4);
  align-items: stretch;
  min-height: 0;
  .panel {
    min-width: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
    border: 1px solid var(--rp-border);
    border-radius: var(--rp-radius-lg);
    background: var(--rp-surface);
    box-shadow: var(--rp-shadow-card);
    overflow: hidden;
  }
  .panel-head {
    flex: 0 0 var(--rp-touch-target);
    min-height: var(--rp-touch-target);
    padding: 0 var(--rp-space-4);
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--rp-border);
    font-size: var(--rp-font-size-13);
    font-weight: var(--rp-weight-bold);
  }
  @media (max-width: 1380px) {
    grid-template-columns: minmax(15rem, 17rem) minmax(0, 1fr);
    .output {
      position: fixed;
      z-index: 20;
      inset: 0 0 0 auto;
      width: min(26rem, 92vw);
      min-height: 100dvh;
      border-radius: 0;
    }
    .output[data-open='false'] {
      display: none;
    }
  }
  @media (max-width: 1023px) {
    grid-template-columns: minmax(0, 1fr);
    .context,
    .output {
      position: fixed;
      z-index: 20;
      inset: 0 auto 0 0;
      width: min(22rem, 92vw);
      min-height: 100dvh;
      border-radius: 0;
    }
    .output {
      inset: 0 0 0 auto;
    }
    .context[data-open='false'],
    .output[data-open='false'] {
      display: none;
    }
    .work {
      min-height: 34rem;
    }
    .panel-head {
      min-height: var(--rp-touch-target);
    }
  }
`;
const IconButton = styled.button<{ $active?: boolean }>`
  min-width: var(--rp-touch-target);
  min-height: var(--rp-touch-target);
  border: 1px solid var(--rp-border);
  border-radius: var(--rp-radius-sm);
  background: ${({ $active }) => ($active ? 'var(--rp-surface-selected)' : 'var(--rp-surface)')};
  color: ${({ $active }) => ($active ? 'var(--rp-action)' : 'var(--rp-ink-subtle)')};
  font-weight: var(--rp-weight-bold);
  &:hover {
    background: var(--rp-surface-subtle);
  }
`;
const ContextBody = styled.nav`
  flex: 1 1 auto;
  min-height: 0;
  padding: var(--rp-space-3);
  overflow-y: auto;
  overscroll-behavior: contain;
  .scope-note {
    font-size: var(--rp-font-size-12);
    line-height: var(--rp-line-normal);
    color: var(--rp-ink-muted);
    margin: 0 0 var(--rp-space-3);
  }
  .document {
    width: 100%;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: var(--rp-space-2);
    align-items: start;
    padding: var(--rp-space-3);
    border: 0;
    border-radius: var(--rp-radius-sm);
    background: transparent;
    text-align: left;
  }
  .document:hover {
    background: var(--rp-surface-subtle);
  }
  .document:has(input:checked) {
    background: var(--rp-surface-selected);
  }
  .document input {
    margin-top: 3px;
    accent-color: var(--rp-action);
  }
  .document strong {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--rp-font-size-13);
  }
  .document small {
    display: block;
    margin-top: var(--rp-space-1);
    color: var(--rp-ink-muted);
    font-size: var(--rp-font-size-12);
  }
  .add {
    width: 100%;
    margin-top: var(--rp-space-3);
  }
`;
const WorkBody = styled.section`
  flex: 1 1 auto;
  min-height: 0;
  padding: var(--rp-space-5);
  display: flex;
  flex-direction: column;
  gap: var(--rp-space-4);
  overflow: hidden;
  .mode {
    display: flex;
    align-items: center;
    gap: var(--rp-space-2);
    font-size: var(--rp-font-size-12);
    color: var(--rp-ink-muted);
  }
  .reparse-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--rp-space-3);
    padding: var(--rp-space-3);
    border: 1px solid var(--rp-border-focus);
    border-radius: var(--rp-radius-sm);
    background: var(--rp-surface-info);
    color: var(--rp-ink-subtle);
    font-size: var(--rp-font-size-12);
    line-height: var(--rp-line-normal);
  }
  .messages {
    display: flex;
    flex: 1 1 auto;
    min-height: 0;
    flex-direction: column;
    gap: var(--rp-space-3);
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: var(--rp-space-1) var(--rp-space-2) var(--rp-space-2) 0;
  }
  .message {
    max-width: min(45rem, 88%);
    padding: var(--rp-space-4);
    border-radius: var(--rp-radius-md);
    font-size: var(--rp-font-size-14);
    line-height: var(--rp-line-normal);
  }
  .message.user {
    margin-left: auto;
    background: var(--rp-action);
    color: var(--rp-action-on);
  }
  .message.answer {
    background: var(--rp-surface-subtle);
  }
  .message.warning {
    background: var(--rp-surface-warning);
    color: var(--rp-status-warning);
  }
  .message.streaming {
    background: var(--rp-surface-info);
  }
  .message.interrupted {
    background: var(--rp-surface-warning);
  }
  .message.failed {
    background: var(--rp-surface-danger);
  }
  .answer-meta {
    margin-top: var(--rp-space-2);
    font-size: var(--rp-font-size-12);
    color: var(--rp-ink-muted);
  }
  .source-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--rp-space-2);
    margin-top: var(--rp-space-3);
  }
  .stream-status {
    margin: var(--rp-space-2) 0 0;
    color: var(--rp-ink-muted);
    font-size: var(--rp-font-size-12);
  }
  .composer {
    display: grid;
    flex: 0 0 auto;
    gap: var(--rp-space-3);
    border-top: 1px solid var(--rp-border);
    margin-top: var(--rp-space-2);
    padding-top: var(--rp-space-4);
  }
  .sensitivity {
    display: flex;
    flex-wrap: wrap;
    gap: var(--rp-space-2);
  }
  .sensitivity-help {
    margin: 0;
    color: var(--rp-ink-muted);
    font-size: var(--rp-font-size-12);
    line-height: var(--rp-line-normal);
  }
  .composer-row {
    display: flex;
    align-items: stretch;
    gap: var(--rp-space-3);
  }
  .composer-row input {
    min-width: 0;
  }
  .reason {
    margin: var(--rp-space-2) 0 0;
    color: var(--rp-status-warning);
    font-size: var(--rp-font-size-12);
  }
  .feedback-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--rp-space-2);
    margin-top: var(--rp-space-3);
  }
`;
const CitationButton = styled.button`
  min-width: 1.5rem;
  min-height: 1.5rem;
  margin-left: var(--rp-space-1);
  padding: 0 var(--rp-space-2);
  border: 1px solid var(--rp-border-focus);
  border-radius: var(--rp-radius-pill);
  background: var(--rp-surface-info);
  color: var(--rp-action-active);
  font-size: var(--rp-font-size-12);
  font-weight: var(--rp-weight-bold);
  vertical-align: baseline;
`;
const OutputBody = styled.aside`
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-height: 0;
  padding: var(--rp-space-4);
  overflow-y: auto;
  overscroll-behavior: contain;
  gap: var(--rp-space-3);
  .output-tabs {
    display: flex;
    gap: var(--rp-space-1);
    flex: 0 0 auto;
    margin: 0 0 var(--rp-space-1);
  }
  .output-tabs button {
    border: 0;
    border-radius: var(--rp-radius-sm);
    background: transparent;
    padding: var(--rp-space-2);
    font-size: var(--rp-font-size-12);
    color: var(--rp-ink-muted);
  }
  .output-tabs button[aria-selected='true'] {
    background: var(--rp-surface-selected);
    color: var(--rp-action);
    font-weight: var(--rp-weight-bold);
  }
  h2 {
    font-size: var(--rp-font-size-16);
    margin: 0;
  }
  p {
    margin: 0;
    font-size: var(--rp-font-size-13);
    line-height: var(--rp-line-normal);
    color: var(--rp-ink-subtle);
  }
  .excerpt {
    padding: var(--rp-space-3);
    border-radius: var(--rp-radius-sm);
    background: var(--rp-surface-info);
    color: var(--rp-ink);
  }
  .release-gate {
    display: grid;
    gap: var(--rp-space-1);
    padding: var(--rp-space-3);
    border: 1px solid var(--rp-border);
    border-radius: var(--rp-radius-sm);
    background: var(--rp-surface-subtle);
  }
  .release-gate strong {
    font-size: var(--rp-font-size-12);
  }
  .release-gate span {
    color: var(--rp-ink-muted);
    font-size: var(--rp-font-size-12);
    line-height: var(--rp-line-normal);
  }
  .retuning {
    display: grid;
    gap: var(--rp-space-3);
    padding: var(--rp-space-3);
    border: 1px solid var(--rp-border);
    border-radius: var(--rp-radius-sm);
    background: var(--rp-surface-subtle);
  }
  .retuning h3 {
    margin: 0;
    font-size: var(--rp-font-size-14);
  }
  .retuning ul {
    display: grid;
    gap: var(--rp-space-1);
    margin: 0;
    padding-left: var(--rp-space-4);
    color: var(--rp-ink-subtle);
    font-size: var(--rp-font-size-12);
    line-height: var(--rp-line-normal);
  }
  .retune-observed {
    color: var(--rp-ink-muted);
    font-size: var(--rp-font-size-12);
  }
  .retune-comparison {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--rp-space-2);
  }
  .retune-comparison div {
    min-width: 0;
    padding: var(--rp-space-2);
    border: 1px solid var(--rp-border);
    border-radius: var(--rp-radius-sm);
  }
  .retune-comparison strong,
  .retune-comparison span {
    display: block;
    font-size: var(--rp-font-size-12);
    overflow-wrap: anywhere;
  }
  .operations {
    display: grid;
    gap: var(--rp-space-3);
    padding: var(--rp-space-3);
    border: 1px solid var(--rp-border);
    border-radius: var(--rp-radius-sm);
    background: var(--rp-surface-subtle);
  }
  .operations h3,
  .operations h4 {
    margin: 0;
    font-size: var(--rp-font-size-14);
  }
  .operations h4 {
    color: var(--rp-ink-muted);
    font-size: var(--rp-font-size-12);
  }
  .operation-history {
    display: grid;
    gap: var(--rp-space-2);
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .operation-history li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--rp-space-2);
    color: var(--rp-ink-subtle);
    font-size: var(--rp-font-size-12);
  }
  .retune-comparison span {
    margin-top: var(--rp-space-1);
    color: var(--rp-ink-muted);
  }
  .spec {
    display: grid;
    gap: var(--rp-space-3);
    margin: 0;
  }
  .spec div {
    border-bottom: 1px solid var(--rp-border);
    padding-bottom: var(--rp-space-2);
  }
  .spec dt {
    font-size: var(--rp-font-size-12);
    color: var(--rp-ink-muted);
  }
  .spec dd {
    margin: var(--rp-space-1) 0 0;
    font-size: var(--rp-font-size-13);
  }
  .manage {
    display: grid;
    gap: var(--rp-space-3);
  }
  .manage-row {
    display: grid;
    gap: var(--rp-space-3);
    justify-content: stretch;
    gap: var(--rp-space-2);
    align-items: center;
    padding: var(--rp-space-3);
    border: 1px solid var(--rp-border);
    border-radius: var(--rp-radius-sm);
    font-size: var(--rp-font-size-12);
  }
  .manage-row span {
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .manage-row-head {
    display: flex;
    justify-content: space-between;
    gap: var(--rp-space-2);
    align-items: center;
  }
  .manage-row-head strong {
    min-width: 0;
    overflow-wrap: anywhere;
    font-size: var(--rp-font-size-13);
  }
  .provenance {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--rp-space-2);
    margin: 0;
  }
  .provenance div {
    min-width: 0;
  }
  .provenance dt {
    color: var(--rp-ink-muted);
    font-size: var(--rp-font-size-11);
  }
  .provenance dd {
    margin: var(--rp-space-1) 0 0;
    overflow-wrap: anywhere;
    font-size: var(--rp-font-size-12);
  }
  .provenance-impact {
    color: var(--rp-ink-muted);
    font-size: var(--rp-font-size-12);
  }
  .evidence-list {
    display: grid;
    gap: var(--rp-space-2);
  }
  .evidence-list button {
    padding: var(--rp-space-2);
    border: 1px solid var(--rp-border);
    border-radius: var(--rp-radius-sm);
    background: var(--rp-surface);
    color: var(--rp-ink);
    font-size: var(--rp-font-size-12);
    text-align: left;
  }
  .evidence-list button[aria-pressed='true'] {
    border-color: var(--rp-border-focus);
    background: var(--rp-surface-selected);
  }
`;
const DialogOverlay = styled.div`
  position: fixed;
  inset: 0;
  z-index: 300;
  display: grid;
  place-items: center;
  background: rgba(29, 36, 51, 0.36);
  padding: var(--rp-space-4);
  .dialog {
    width: min(34rem, 100%);
    padding: var(--rp-space-6);
    border-radius: var(--rp-radius-lg);
    background: var(--rp-surface);
    box-shadow: var(--rp-shadow-raised);
  }
  .dialog h2 {
    margin: 0 0 var(--rp-space-2);
    font-size: var(--rp-font-size-20);
  }
  .dialog p {
    font-size: var(--rp-font-size-14);
    line-height: var(--rp-line-normal);
    color: var(--rp-ink-subtle);
  }
  .choices {
    display: grid;
    gap: var(--rp-space-2);
    margin: var(--rp-space-4) 0;
  }
  .choice {
    display: block;
    padding: var(--rp-space-3);
    border: 1px solid var(--rp-border);
    border-radius: var(--rp-radius-sm);
    font-size: var(--rp-font-size-13);
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--rp-space-2);
    margin-top: var(--rp-space-5);
  }
`;

function focusable(root: HTMLElement | null) {
  return root?.querySelector<HTMLElement>(
    'button, input, select, textarea, [tabindex]:not([tabindex="-1"])',
  );
}
function trapTab(event: ReactKeyboardEvent<HTMLElement>) {
  if (event.key !== 'Tab') return;
  const items = Array.from(
    event.currentTarget.querySelectorAll<HTMLElement>(
      'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])',
    ),
  );
  if (!items.length) return;
  const first = items[0];
  const last = items[items.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

export function RagDetailPage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<RagInstanceDetail>();
  const [executionPlan, setExecutionPlan] = useState<ExecutionPlan>();
  const [modelRuntime, setModelRuntime] = useState<ModelServiceStatus[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [answer, setAnswer] = useState<ChatAnswer>();
  const [lastQuestion, setLastQuestion] = useState('');
  const [streamingAnswer, setStreamingAnswer] = useState<StreamingAnswer>();
  const [draft, setDraft] = useState('');
  const [sensitivity, setSensitivity] = useState('balanced');
  const [open, setOpen] = useState<Record<PanelName, boolean>>(() =>
    initialPanels(typeof window === 'undefined' ? 1440 : window.innerWidth),
  );
  const [view, setView] = useState<OutputView>('settings');
  const [evidence, setEvidence] = useState<PipelineCandidate>();
  const [evidenceIndex, setEvidenceIndex] = useState(0);
  const [dialog, setDialog] = useState<WorkspaceDialog>();
  const [targetId, setTargetId] = useState<string>();
  const [files, setFiles] = useState<File[]>([]);
  const [reuse, setReuse] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [queryError, setQueryError] = useState<string>();
  const [preflightConflictIds, setPreflightConflictIds] = useState<string[]>();
  const [failedSearch, setFailedSearch] = useState<{
    question: string;
    context: SearchContextSnapshot;
    stopped?: boolean;
  }>();
  const [evidenceLoadError, setEvidenceLoadError] = useState<string>();
  const [feedback, setFeedback] = useState<1 | -1>();
  const [reindexRetrying, setReindexRetrying] = useState(false);
  const [retuneStarting, setRetuneStarting] = useState(false);
  const [retuneError, setRetuneError] = useState<string>();
  const [reparsingDocumentId, setReparsingDocumentId] = useState<string>();
  const [reparseExcludedIds, setReparseExcludedIds] = useState<string[]>([]);
  const [reparseNotice, setReparseNotice] = useState<string>();
  const [reparseError, setReparseError] = useState<string>();
  const [jobHistory, setJobHistory] = useState<RagProcessingJob[]>();
  const [jobRetrying, setJobRetrying] = useState<string>();
  const evidenceHeadingRef = useRef<HTMLHeadingElement | null>(null);
  const evidenceTriggerRef = useRef<HTMLButtonElement | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const dialogTriggerRef = useRef<HTMLElement | null>(null);
  const panelTriggerRefs = useRef<Partial<Record<PanelName, HTMLButtonElement>>>({});
  const answerAbortRef = useRef<AbortController>();
  const load = () =>
    Promise.all([ragApi.get(id), ragApi.executionPlan(id), ragApi.modelRuntime(), ragApi.jobs(id)])
      .then(([item, plan, runtime, jobs]) => {
        setDetail(item);
        setExecutionPlan(plan);
        setModelRuntime(runtime);
        setJobHistory(jobs);
        setSelectedIds((prior) =>
          prior.length
            ? prior.filter((value) =>
                item.documents.some(
                  (document) =>
                    document.id === value &&
                    documentIsSearchReady(document) &&
                    !reparseExcludedIds.includes(document.id),
                ),
              )
            : item.documents
                .filter(
                  (document) =>
                    documentIsSearchReady(document) && !reparseExcludedIds.includes(document.id),
                )
                .map((document) => document.id),
        );
      })
      .catch((item: Error) => setError(item.message));
  useEffect(() => {
    load();
  }, [id]);
  const [viewportWidth, setViewportWidth] = useState(() =>
    typeof window === 'undefined' ? 1440 : window.innerWidth,
  );
  const viewportWidthRef = useRef(viewportWidth);
  useEffect(() => {
    const updateViewport = () => {
      const nextWidth = window.innerWidth;
      const previousWidth = viewportWidthRef.current;
      viewportWidthRef.current = nextWidth;
      setViewportWidth(nextWidth);
      setOpen((current) => {
        if (nextWidth >= 1380) return previousWidth < 1380 ? initialPanels(nextWidth) : current;
        if (nextWidth >= 1024)
          return previousWidth < 1024 || previousWidth >= 1380 ? initialPanels(nextWidth) : current;
        if (previousWidth >= 1024) return initialPanels(nextWidth);
        return current.context && current.output ? initialPanels(nextWidth) : current;
      });
    };
    window.addEventListener('resize', updateViewport);
    return () => window.removeEventListener('resize', updateViewport);
  }, []);
  useEffect(() => {
    if (evidence) {
      setView('evidence');
      window.setTimeout(() => evidenceHeadingRef.current?.focus(), 0);
    }
  }, [evidence]);
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && evidence && !evidenceLoadError) {
        setEvidence(undefined);
        evidenceTriggerRef.current?.focus();
      }
      if (event.key === 'Escape' && dialog) closeDialog();
      if (event.key === 'Escape' && !dialog && !evidence && viewportWidth < 1440) {
        if (open.output) {
          setOpen((state) => ({ ...state, output: false }));
          panelTriggerRefs.current.output?.focus();
        } else if (open.context && viewportWidth < 1024) {
          setOpen((state) => ({ ...state, context: false }));
          panelTriggerRefs.current.context?.focus();
        }
      }
    };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [evidence, dialog, evidenceLoadError, open.context, open.output, viewportWidth]);
  useEffect(() => {
    if (dialog) window.setTimeout(() => focusable(dialogRef.current)?.focus(), 0);
  }, [dialog]);
  useEffect(() => () => answerAbortRef.current?.abort(), []);
  useEffect(() => {
    const activeJob = [detail?.latestJob, detail?.fullReindexJob].some(
      (job) => job && !['SUCCEEDED', 'FAILED', 'CANCELLED'].includes(job.state),
    );
    if (!activeJob) return;
    const timer = window.setInterval(load, 2000);
    return () => window.clearInterval(timer);
  }, [
    detail?.latestJob?.id,
    detail?.latestJob?.state,
    detail?.fullReindexJob?.id,
    detail?.fullReindexJob?.state,
  ]);
  if (error) return <ErrorState message={error} retry={load} />;
  if (!detail) return <LoadingState label="지식 공간과 문서를 불러오고 있어요…" />;
  const toggleDocument = (documentId: string) => {
    if (
      busy ||
      reparseExcludedIds.includes(documentId) ||
      !documentIsSearchReady(detail.documents.find((document) => document.id === documentId))
    )
      return;
    setSelectedIds((ids) =>
      ids.includes(documentId) ? ids.filter((item) => item !== documentId) : [...ids, documentId],
    );
  };
  const togglePanel = (panel: PanelName) =>
    setOpen((state) => {
      const nextOpen = !state[panel];
      if (typeof window !== 'undefined' && window.innerWidth < 1024 && nextOpen)
        return panel === 'context'
          ? { context: true, output: false }
          : { context: false, output: true };
      return { ...state, [panel]: nextOpen };
    });
  const showPanel = (panel: PanelName) =>
    setOpen((state) =>
      typeof window !== 'undefined' && window.innerWidth < 1024
        ? panel === 'context'
          ? { context: true, output: false }
          : { context: false, output: true }
        : { ...state, [panel]: true },
    );
  const readyDocuments = detail.documents.filter(
    (document) => documentIsSearchReady(document) && !reparseExcludedIds.includes(document.id),
  );
  const reindexBlockedDocuments = detail.documents.filter(
    (document) =>
      selectedIds.includes(document.id) &&
      document.fullReindexRequired &&
      !document.fullReindexReady,
  );
  const reindexBlockedNames = reindexBlockedDocuments.map((document) => document.name).join(', ');
  const searchDisabled =
    selectedIds.length === 0 || !draft.trim() || busy || reindexBlockedDocuments.length > 0;
  const disabledReason = !selectedIds.length
    ? '먼저 검색할 문서를 하나 이상 선택해 주세요.'
    : reindexBlockedDocuments.length
      ? `${reindexBlockedNames}은(는) 전체 문서 색인이 완료될 때까지 검색할 수 없어요. 문서 선택을 해제하거나 색인이 끝난 뒤 다시 시도해 주세요.`
      : !draft.trim()
        ? '질문을 입력하면 검색할 수 있어요.'
        : busy
          ? '검색 결과와 근거를 준비하고 있어요.'
          : '';
  const ask = async (question = draft, contextOverride?: SearchContextSnapshot) => {
    if (busy || !question.trim() || reindexBlockedDocuments.length) return;
    const context = contextOverride ?? {
      documentIds: [...selectedIds],
      documentNames: detail.documents
        .filter((document) => selectedIds.includes(document.id))
        .map((document) => document.name),
      sensitivity,
    };
    if (!context.documentIds.length) return;
    const controller = new AbortController();
    answerAbortRef.current = controller;
    setBusy(true);
    setQueryError(undefined);
    setPreflightConflictIds(undefined);
    setFailedSearch(undefined);
    setStreamingAnswer({
      question,
      text: '',
      citations: [],
      generation: { status: 'GROUNDING', fallback: false },
      context,
      state: 'streaming',
    });
    try {
      const nextAnswer = await ragApi.streamAnswer(
        id,
        question,
        context.documentIds,
        context.sensitivity,
        {
          signal: controller.signal,
          onUpdate: (partial) =>
            setStreamingAnswer((current) =>
              current ? { ...current, ...partial, state: 'streaming' } : current,
            ),
        },
      );
      if (controller.signal.aborted) return;
      setAnswer({ ...nextAnswer, context });
      setLastQuestion(question);
      setFeedback(undefined);
      setStreamingAnswer(undefined);
    } catch (item) {
      if ((item as Error).name === 'AbortError') {
        setStreamingAnswer((current) => (current ? { ...current, state: 'interrupted' } : current));
        setFailedSearch({ question, context, stopped: true });
      } else {
        setQueryError(
          item instanceof SearchPreflightError
            ? preflightConflictCopy(item, detail.documents)
            : (item as Error).message,
        );
        setPreflightConflictIds(
          item instanceof SearchPreflightError ? item.documentIds : undefined,
        );
        setStreamingAnswer((current) => (current ? { ...current, state: 'failed' } : current));
        setFailedSearch({ question, context });
      }
    } finally {
      if (answerAbortRef.current === controller) setBusy(false);
    }
  };
  const stopAnswer = () => answerAbortRef.current?.abort();
  const retryFullReindex = async () => {
    if (!detail.fullReindexJob?.canRetry || reindexRetrying) return;
    setReindexRetrying(true);
    try {
      await ragApi.retryJob(detail.fullReindexJob.id);
      setDetail(await ragApi.get(id));
    } finally {
      setReindexRetrying(false);
    }
  };
  const retryOperationalJob = async (job: RagProcessingJob) => {
    if (!job.canRetry || jobRetrying) return;
    setJobRetrying(job.id);
    try {
      await ragApi.retryJob(job.id);
      await load();
    } finally {
      setJobRetrying(undefined);
    }
  };
  const startRetune = async () => {
    const signal = detail.retuningSignal;
    if (
      !signal?.recommended ||
      signal.action !== 'START_RETUNE' ||
      !signal.eligibleDocumentIds.length ||
      retuneStarting
    )
      return;
    setRetuneStarting(true);
    setRetuneError(undefined);
    try {
      await ragApi.retune(id, signal.eligibleDocumentIds, signal.reasons[0]);
      const updated = await ragApi.get(id);
      setDetail(updated);
      navigate(`/rag/${id}/setup`);
    } catch (item) {
      setRetuneError((item as Error).message || '재튜닝 준비를 시작하지 못했어요.');
    } finally {
      setRetuneStarting(false);
    }
  };
  const contextSummary = (context: SearchContextSnapshot) =>
    `${context.documentNames.join(', ') || '선택한 문서'} · ${sensitivityLabels[context.sensitivity] ?? context.sensitivity}`;
  const leaveFeedback = async (rating: 1 | -1) => {
    if (!answer) return;
    setFeedback(rating);
    await ragApi.feedback(id, rating, {
      artifactId: answer.artifactId,
      documentIds: answer.context?.documentIds,
      citationIds: answer.citations.map((citation) => citation.id),
    });
  };
  const closeDialog = () => {
    setDialog(undefined);
    window.setTimeout(() => dialogTriggerRef.current?.focus(), 0);
  };
  const openDialog = (kind: WorkspaceDialog, trigger: HTMLElement, documentId?: string) => {
    dialogTriggerRef.current = trigger;
    if (documentId) setTargetId(documentId);
    setDialog(kind);
  };
  const loadEvidenceCitation = async (candidate: PipelineCandidate, index: number) => {
    const citation = candidate.evidence[index];
    if (!citation?.navigateUrl) return;
    try {
      const source = await ragApi.evidence(citation.navigateUrl);
      setEvidence((current) =>
        current?.id === candidate.id
          ? {
              ...current,
              evidence: current.evidence.map((item) =>
                item.id === citation.id ? { ...item, ...source } : item,
              ),
            }
          : current,
      );
    } catch (item) {
      setEvidenceLoadError((item as Error).message);
    }
  };
  const selectEvidenceCitation = (candidate: PipelineCandidate, index: number) => {
    setEvidenceIndex(index);
    setEvidenceLoadError(undefined);
    void loadEvidenceCitation(candidate, index);
  };
  function citationButton(citation: ChatAnswer['citations'][number], index: number) {
    return (
      <CitationButton
        key={citation.id}
        ref={index === 0 ? evidenceTriggerRef : undefined}
        aria-label={`${citation.title} 근거 열기`}
        title={`${citation.title}: ${citation.excerpt}`}
        onClick={(event) =>
          openEvidence(
            {
              id: citation.id,
              chunkingStrategy: 'FIXED',
              retrievalConfig: 'HYBRID',
              label: citation.title,
              plainLabel: '근거',
              description: citation.page,
              selectionCount: 0,
              latencyMs: 0,
              answer: '',
              evidence: [citation],
            },
            event.currentTarget,
          )
        }
      >
        {index + 1}
      </CitationButton>
    );
  }
  const openEvidence = async (candidate: PipelineCandidate, trigger: HTMLButtonElement) => {
    evidenceTriggerRef.current = trigger;
    showPanel('output');
    setEvidence(candidate);
    setEvidenceIndex(0);
    setEvidenceLoadError(undefined);
    await loadEvidenceCitation(candidate, 0);
  };
  const addDocuments = async () => {
    if (!files.length) return;
    setBusy(true);
    try {
      const updated = await ragApi.upload(id, files, reuse);
      setDetail(updated);
      setSelectedIds(
        updated.documents.filter((document) => document.pipelineId).map((document) => document.id),
      );
      setDialog(undefined);
      if (!reuse) navigate(`/rag/${id}/setup`);
    } finally {
      setBusy(false);
    }
  };
  const deleteDocument = async () => {
    if (!targetId) return;
    setBusy(true);
    try {
      await ragApi.deleteDocument(id, targetId);
      setDialog(undefined);
      setTargetId(undefined);
      await load();
    } finally {
      setBusy(false);
    }
  };
  const reparseDocument = async (documentId: string) => {
    if (reparsingDocumentId) return;
    setReparsingDocumentId(documentId);
    setReparseError(undefined);
    setReparseNotice(undefined);
    try {
      await ragApi.reparseDocument(id, documentId);
      setSelectedIds((ids) => ids.filter((selectedId) => selectedId !== documentId));
      setReparseExcludedIds((ids) => (ids.includes(documentId) ? ids : [...ids, documentId]));
      const updated = await ragApi.get(id);
      setDetail(updated);
      const documentName =
        updated.documents.find((document) => document.id === documentId)?.name ?? '이 문서';
      setReparseNotice(
        `${documentName}을(를) 다시 읽고 있어요 · 검색 범위에서 제외됨 · 완료 후 다시 비교해 주세요.`,
      );
    } catch {
      setReparseError('재파싱을 시작하지 못했어요. 원본 보관 상태를 확인한 뒤 다시 시도해 주세요.');
    } finally {
      setReparsingDocumentId(undefined);
    }
  };
  const citationGroups = answer
    ? Object.values(
        answer.citations.reduce<
          Record<string, { documentName: string; citations: ChatAnswer['citations'] }>
        >((groups, citation) => {
          const key = citation.documentId ?? citation.documentName ?? citation.title;
          const group = groups[key] ?? {
            documentName: citation.documentName ?? citation.title,
            citations: [],
          };
          group.citations.push(citation);
          groups[key] = group;
          return groups;
        }, {}),
      )
    : [];
  const coveredDocumentCount =
    answer?.documentCoverage?.filter((coverage) => coverage.citationCount > 0).length ??
    citationGroups.length;
  const activeEvidenceCitation = evidence?.evidence[evidenceIndex];
  const fullReindexJob = detail.fullReindexJob;
  const operationalJobs = jobHistory ?? (detail.latestJob ? [detail.latestJob] : []);
  const primaryOperationalJob = detail.latestJob ?? operationalJobs[0];
  const outputIsDrawer = viewportWidth < 1440;
  const contextIsDrawer = viewportWidth < 1024;
  const panelId = (panel: PanelName) => `rag-${id}-${panel}-panel`;
  return (
    <DetailPage>
      <Header>
        <div>
          <StatusBadge status={detail.status} />
          <h1>{detail.name}</h1>
          <p>문서 범위를 고르고, 답변과 근거를 함께 확인하세요.</p>
          {detail.latestJob && (
            <p className="job-summary" role="status">
              {detail.latestJob.state === 'SUCCEEDED' ? '최근 문서 준비' : '문서 준비 중'}:{' '}
              {detail.latestJob.currentStep} · {detail.latestJob.completed}/{detail.latestJob.total}{' '}
              단계 완료
            </p>
          )}
          {fullReindexJob && (
            <p className="job-summary" role="status">
              {fullReindexJob.state === 'SUCCEEDED'
                ? '전체 문서 색인 완료: 현재 검색에 전체 문서가 반영됐어요.'
                : fullReindexJob.state === 'FAILED'
                  ? '전체 문서 색인을 마치지 못했어요. 다시 시도한 뒤 전체 문서 검색을 사용할 수 있어요.'
                  : `전체 문서 색인 중: ${fullReindexJob.currentStep}${fullReindexJob.total ? ` · ${fullReindexJob.completed}/${fullReindexJob.total} 단계 완료` : ''} · 완료 전에는 해당 문서 검색을 잠시 기다려 주세요.`}
              {fullReindexJob.state === 'FAILED' && fullReindexJob.canRetry && (
                <Button
                  $variant="ghost"
                  onClick={() => void retryFullReindex()}
                  disabled={reindexRetrying}
                >
                  {reindexRetrying ? '전체 색인 다시 준비 중…' : '전체 색인 다시 시도'}
                </Button>
              )}
            </p>
          )}
        </div>
        <div className="tools">
          <IconButton
            ref={(node) => {
              panelTriggerRefs.current.context = node ?? undefined;
            }}
            $active={open.context}
            aria-label="문서 컨텍스트 패널 표시 전환"
            aria-expanded={open.context}
            aria-pressed={open.context}
            aria-controls={panelId('context')}
            onClick={() => togglePanel('context')}
          >
            문서
          </IconButton>
          <IconButton
            ref={(node) => {
              panelTriggerRefs.current.output = node ?? undefined;
            }}
            $active={open.output}
            aria-label="결과 및 근거 패널 표시 전환"
            aria-expanded={open.output}
            aria-pressed={open.output}
            aria-controls={panelId('output')}
            onClick={() => togglePanel('output')}
          >
            근거
          </IconButton>
        </div>
      </Header>
      <Workspace aria-label="RAG 검색 작업 공간">
        <section
          id={panelId('context')}
          className="panel context"
          data-open={open.context}
          aria-label="문서 컨텍스트"
          role={contextIsDrawer && open.context ? 'dialog' : undefined}
          aria-modal={contextIsDrawer && open.context ? true : undefined}
          onKeyDown={contextIsDrawer && open.context ? trapTab : undefined}
        >
          <div className="panel-head">
            <span>Context · 문서 범위</span>
            <span>
              {selectedIds.length}/{readyDocuments.length}
            </span>
          </div>
          <ContextBody aria-label="검색 문서 선택">
            <p className="scope-note">
              선택한 문서만 검색합니다. 문서 관리는 근거 패널에서 할 수 있어요.
            </p>
            {detail.documents.length ? (
              detail.documents.map((document) => (
                <div className="document" key={document.id}>
                  <input
                    id={`doc-${document.id}`}
                    type="checkbox"
                    checked={selectedIds.includes(document.id)}
                    disabled={
                      busy ||
                      !documentIsSearchReady(document) ||
                      reparseExcludedIds.includes(document.id)
                    }
                    onChange={() => toggleDocument(document.id)}
                    aria-describedby={`doc-meta-${document.id}`}
                  />
                  <label htmlFor={`doc-${document.id}`}>
                    <strong>{document.name}</strong>
                    <small id={`doc-meta-${document.id}`}>
                      {document.fullReindexRequired && !document.fullReindexReady
                        ? '전체 색인 중 · 이 문서는 검색 대기'
                        : (document.pipelineLabel ?? '아직 비교가 필요해요')}
                    </small>
                  </label>
                  <IconButton
                    aria-label={`${document.name} 문서 관리 열기`}
                    onClick={() => {
                      setView('documents');
                      showPanel('output');
                    }}
                  >
                    ⋯
                  </IconButton>
                </div>
              ))
            ) : (
              <p className="scope-note">
                아직 문서가 없어요. 문서를 추가하면 준비 상태를 여기서 확인할 수 있어요.
              </p>
            )}
            <Button
              className="add"
              $variant="secondary"
              onClick={(event) => openDialog('add', event.currentTarget)}
            >
              + 문서 추가
            </Button>
          </ContextBody>
        </section>
        <section className="panel work" aria-label="검색 작업">
          <div className="panel-head">
            <span>Work · 검색</span>
            <span role="status" aria-live="polite">
              {busy
                ? '검색 결과와 근거를 준비하고 있어요…'
                : selectedIds.length
                  ? `${selectedIds.length}개 문서 선택됨`
                  : '문서를 선택해 주세요'}
            </span>
          </div>
          <WorkBody>
            {reparseNotice && (
              <div className="reparse-banner" role="status">
                <span>{reparseNotice}</span>
                <Button
                  $variant="ghost"
                  onClick={() => {
                    setView('documents');
                    showPanel('output');
                  }}
                >
                  작업 상태 보기
                </Button>
              </div>
            )}
            <div className="mode">
              <Pill $tone="brand">실사용 검색</Pill>
              <span>기술 설정은 필요할 때만 근거 패널에서 확인할 수 있어요.</span>
            </div>
            <div className="messages" aria-live="off" aria-busy={busy}>
              {answer ? (
                <>
                  <div className="message user">{lastQuestion}</div>
                  <div className={`message ${answer.citations.length ? 'answer' : 'warning'}`}>
                    {answer.text}
                    {answer.citations.map(citationButton)}
                    <div className="answer-meta">
                      {answer.citations.length
                        ? `근거 ${answer.citations.length}개 · 응답 ${(answer.latencyMs / 1000).toFixed(1)}초`
                        : '근거 부족 · 검색 범위 또는 질문을 바꿔 보세요.'}
                    </div>
                    {answer.context && (
                      <div className="answer-meta">검색 범위: {contextSummary(answer.context)}</div>
                    )}
                    {answer.runtime?.fallback && (
                      <div className="answer-meta" role="status">
                        개발용 fallback 검색 결과 ·{' '}
                        {answer.runtime.warning ?? answer.runtime.provider}
                      </div>
                    )}
                    {answer.generation && (
                      <div className="answer-meta" role="status">
                        {answer.generation.fallback
                          ? fallbackGenerationCopy(
                              answer.generation.fallbackReason,
                              answer.generation.detail,
                            )
                          : '문서 근거를 바탕으로 정리한 답변이에요.'}
                      </div>
                    )}
                    {citationGroups.length > 1 && (
                      <>
                        <div className="answer-meta" role="status">
                          {coveredDocumentCount}개 문서의 근거를 함께 확인했어요.
                        </div>
                        <div className="source-actions" aria-label="문서별 인용 근거">
                          {citationGroups.map((group) => (
                            <Button
                              key={group.documentName}
                              $variant="ghost"
                              onClick={(event) =>
                                void openEvidence(
                                  {
                                    id: `source-${group.documentName}`,
                                    chunkingStrategy: 'FIXED',
                                    retrievalConfig: 'HYBRID',
                                    label: group.documentName,
                                    plainLabel: '문서 근거',
                                    description: '답변에 인용된 문서 근거',
                                    selectionCount: 0,
                                    latencyMs: 0,
                                    answer: '',
                                    evidence: group.citations,
                                  },
                                  event.currentTarget,
                                )
                              }
                            >
                              {group.documentName} 근거 {group.citations.length}개 보기
                            </Button>
                          ))}
                        </div>
                      </>
                    )}
                    <div className="feedback-actions" aria-label="검색 결과 피드백">
                      <Button
                        $variant="ghost"
                        onClick={() => void leaveFeedback(1)}
                        aria-pressed={feedback === 1}
                      >
                        도움돼요
                      </Button>
                      <Button
                        $variant="ghost"
                        onClick={() => void leaveFeedback(-1)}
                        aria-pressed={feedback === -1}
                      >
                        개선 필요
                      </Button>
                      {answer.context && (
                        <Button
                          $variant="ghost"
                          onClick={() => void ask(lastQuestion, answer.context)}
                        >
                          같은 조건으로 다시 검색
                        </Button>
                      )}
                    </div>
                  </div>
                </>
              ) : !streamingAnswer ? (
                <div className="message answer">
                  궁금한 점을 질문해 보세요. 답변에는 확인할 수 있는 문서 근거가 함께 표시됩니다.
                </div>
              ) : null}
              {streamingAnswer && (
                <>
                  <div className="message user">{streamingAnswer.question}</div>
                  <div className={`message ${streamingAnswer.state}`}>
                    {streamingAnswer.text ||
                      `${generationStatusCopy(streamingAnswer.generation?.status)}…`}
                    {streamingAnswer.citations.map(citationButton)}
                    <p className="stream-status" role="status">
                      {streamingAnswer.state === 'streaming'
                        ? `${generationStatusCopy(streamingAnswer.generation?.status)} 필요하면 이 화면의 표시를 중단할 수 있어요.`
                        : streamingAnswer.state === 'interrupted'
                          ? '이 화면의 답변 표시를 중단했어요. 서버 작업은 계속될 수 있어요. 지금까지 받은 내용은 남아 있어요.'
                          : '검색 결과 연결이 끊겼어요. 지금까지 받은 내용을 확인하거나 다시 질문해 주세요.'}
                    </p>
                    <div className="answer-meta">
                      검색 범위: {contextSummary(streamingAnswer.context)}
                    </div>
                  </div>
                </>
              )}
            </div>
            <div className="composer">
              <div
                className="sensitivity"
                role="group"
                aria-describedby="sensitivity-help"
                aria-label="검색 민감도"
              >
                {[
                  ['flexible', '유연하게'],
                  ['balanced', '평이하게'],
                  ['strict', '엄격하게'],
                ].map(([value, label]) => (
                  <IconButton
                    key={value}
                    $active={sensitivity === value}
                    aria-pressed={sensitivity === value}
                    onClick={() => setSensitivity(value)}
                  >
                    {label}
                  </IconButton>
                ))}
              </div>
              <p className="sensitivity-help" id="sensitivity-help">
                {sensitivityDescriptions[sensitivity]}
              </p>
              <div className="composer-row">
                <Input
                  aria-label="검색 질문"
                  value={draft}
                  disabled={busy || !readyDocuments.length || reindexBlockedDocuments.length > 0}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.nativeEvent.isComposing) ask();
                  }}
                  placeholder="예: 국내 출장 숙박비는 얼마까지 되나요?"
                />
                {busy ? (
                  <Button $variant="secondary" onClick={stopAnswer}>
                    표시 중단
                  </Button>
                ) : (
                  <Button
                    onClick={() => ask()}
                    disabled={searchDisabled}
                    aria-describedby={disabledReason ? 'composer-reason' : undefined}
                  >
                    질문하기
                  </Button>
                )}
              </div>
              {queryError && (
                <div className="reason" role="alert">
                  <p>{queryError}</p>
                  {failedSearch && !failedSearch.stopped && (
                    <Button
                      $variant="secondary"
                      onClick={() => void ask(failedSearch.question, failedSearch.context)}
                    >
                      같은 조건으로 다시 시도
                    </Button>
                  )}
                  {failedSearch && (
                    <Button
                      $variant="ghost"
                      onClick={() => {
                        setDraft(failedSearch.question);
                        setQueryError(undefined);
                      }}
                    >
                      질문 수정하기
                    </Button>
                  )}
                  {preflightConflictIds?.length && (
                    <Button
                      $variant="ghost"
                      onClick={() => {
                        showPanel('context');
                        window.setTimeout(() => {
                          const firstConflict = preflightConflictIds[0];
                          document.getElementById(`doc-${firstConflict}`)?.focus();
                        }, 0);
                      }}
                    >
                      문서 선택 조정하기
                    </Button>
                  )}
                </div>
              )}
              {failedSearch?.stopped && !queryError && (
                <div className="reason" role="status">
                  <p>이 질문을 같은 문서 범위로 다시 검색할 수 있어요.</p>
                  <Button
                    $variant="secondary"
                    onClick={() => void ask(failedSearch.question, failedSearch.context)}
                  >
                    이 질문 다시 보내기
                  </Button>
                </div>
              )}
              {disabledReason && (
                <p className="reason" id="composer-reason">
                  {disabledReason}
                </p>
              )}
            </div>
          </WorkBody>
        </section>
        <section
          id={panelId('output')}
          className="panel output"
          data-open={open.output}
          aria-label="결과 및 근거"
          role={outputIsDrawer && open.output ? 'dialog' : undefined}
          aria-modal={outputIsDrawer && open.output ? true : undefined}
          onKeyDown={outputIsDrawer && open.output ? trapTab : undefined}
        >
          <div className="panel-head">
            <span>
              Output · {view === 'evidence' ? '근거' : view === 'documents' ? '문서 관리' : '설정'}
            </span>
            <IconButton aria-label="결과 패널 접기" onClick={() => togglePanel('output')}>
              ×
            </IconButton>
          </div>
          <OutputBody aria-label={evidence ? '문서 근거' : undefined}>
            <div className="output-tabs" role="tablist" aria-label="결과 패널 보기">
              {(['evidence', 'settings', 'documents'] as OutputView[]).map(
                (tabView, index, views) => (
                  <button
                    key={tabView}
                    id={`rag-${id}-output-tab-${tabView}`}
                    role="tab"
                    aria-selected={view === tabView}
                    aria-controls={`rag-${id}-output-panel-${tabView}`}
                    tabIndex={view === tabView ? 0 : -1}
                    onClick={() => setView(tabView)}
                    onKeyDown={(event) => {
                      const direction =
                        event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
                      const nextIndex =
                        event.key === 'Home'
                          ? 0
                          : event.key === 'End'
                            ? views.length - 1
                            : (index + direction + views.length) % views.length;
                      if (direction || event.key === 'Home' || event.key === 'End') {
                        event.preventDefault();
                        const nextView = views[nextIndex];
                        setView(nextView);
                        window.setTimeout(
                          () =>
                            document.getElementById(`rag-${id}-output-tab-${nextView}`)?.focus(),
                          0,
                        );
                      }
                    }}
                  >
                    {tabView === 'evidence' ? '근거' : tabView === 'settings' ? '설정' : '문서'}
                  </button>
                ),
              )}
            </div>
            <div
              role="tabpanel"
              id={`rag-${id}-output-panel-${view}`}
              aria-labelledby={`rag-${id}-output-tab-${view}`}
              tabIndex={0}
            >
              {view === 'evidence' ? (
                evidence ? (
                  <>
                    {evidence.evidence.length > 1 && (
                      <div className="evidence-list" role="list" aria-label="이 문서의 인용 근거">
                        {evidence.evidence.map((citation, index) => (
                          <div key={citation.id} role="listitem">
                            <button
                              type="button"
                              aria-pressed={evidenceIndex === index}
                              onClick={() => selectEvidenceCitation(evidence, index)}
                            >
                              {citation.page} · {citation.excerpt.slice(0, 56)}
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                    <Pill $tone="brand">{activeEvidenceCitation?.page}</Pill>
                    <h2 ref={evidenceHeadingRef} tabIndex={-1}>
                      {activeEvidenceCitation?.title}
                    </h2>
                    <p className="excerpt">{activeEvidenceCitation?.excerpt}</p>
                    {evidenceLoadError && (
                      <div className="excerpt" role="alert">
                        <p>{evidenceLoadError}</p>
                        <p>원문 전체를 불러오지 못해 인용 미리보기를 보여드려요.</p>
                        <Button
                          $variant="secondary"
                          onClick={() => void loadEvidenceCitation(evidence, evidenceIndex)}
                        >
                          근거 다시 불러오기
                        </Button>
                      </div>
                    )}
                    <Button
                      $variant="ghost"
                      onClick={() => {
                        setEvidence(undefined);
                        evidenceTriggerRef.current?.focus();
                      }}
                    >
                      근거 닫기
                    </Button>
                  </>
                ) : (
                  <>
                    <h2>근거를 확인하세요</h2>
                    <p>
                      답변 속 번호를 누르면 해당 문서 조각이 여기에 열립니다. 근거가 없는 답은
                      경고로 구분됩니다.
                    </p>
                  </>
                )
              ) : view === 'settings' ? (
                <>
                  <h2>확정된 설정</h2>
                  {(() => {
                    const requiredServices = executionPlan?.requiredServices.length
                      ? executionPlan.requiredServices
                      : modelRuntime;
                    const unavailable = requiredServices.filter((service) => !service.ready);
                    const ready = Boolean(executionPlan?.ready) && unavailable.length === 0;
                    return (
                      <div className="release-gate" role="status" aria-label="배포 전 런타임 점검">
                        <strong>개발자 점검 · 런타임 {ready ? '준비됨' : '확인 필요'}</strong>
                        <span>
                          {ready
                            ? `필수 서비스 ${requiredServices.length}개가 준비되었습니다.`
                            : unavailable.length
                              ? `연결 필요: ${unavailable.map((service) => runtimeTechniqueLabel(service.technique)).join(', ')}`
                              : '필수 서비스 상태를 불러오는 중입니다.'}
                        </span>
                        <Button $variant="ghost" onClick={load}>
                          상태 새로고침
                        </Button>
                      </div>
                    );
                  })()}
                  {!executionPlan?.ready && (
                    <p className="excerpt" role="status">
                      실제 모델 서비스가 아직 준비되지 않아 개발용 fallback 검색 결과가 표시될 수
                      있어요.
                    </p>
                  )}
                  {primaryOperationalJob && (
                    <section className="operations" aria-label="문서 작업 상태">
                      <h3>문서 작업 상태</h3>
                      <div role="status" aria-live="polite">
                        <Pill $tone={operationalJobTone(primaryOperationalJob)}>
                          {operationalJobCopy(primaryOperationalJob)}
                        </Pill>
                        <p>
                          {primaryOperationalJob.currentStep} · {primaryOperationalJob.completed}/
                          {primaryOperationalJob.total || '?'} 단계 완료
                          {primaryOperationalJob.attempt && primaryOperationalJob.attempt > 0
                            ? ` · 재시도 ${primaryOperationalJob.attempt}회`
                            : ''}
                        </p>
                      </div>
                      {primaryOperationalJob.canRetry && (
                        <Button
                          $variant="secondary"
                          onClick={() => void retryOperationalJob(primaryOperationalJob)}
                          disabled={Boolean(jobRetrying)}
                        >
                          {jobRetrying === primaryOperationalJob.id
                            ? '복구 준비 중…'
                            : '이 작업 다시 시도'}
                        </Button>
                      )}
                      {jobHistory ? (
                        <>
                          <h4>최근 작업</h4>
                          <ul className="operation-history" aria-label="최근 문서 작업 이력">
                            {operationalJobs.slice(0, 5).map((job) => (
                              <li key={job.id}>
                                <span>{operationalJobCopy(job)}</span>
                                <span>
                                  {job.completed}/{job.total || '?'} 단계
                                  {job.attempt && job.attempt > 0
                                    ? ` · 재시도 ${job.attempt}회`
                                    : ''}
                                </span>
                              </li>
                            ))}
                          </ul>
                        </>
                      ) : (
                        <p>최근 작업 이력은 준비되면 이곳에서 확인할 수 있어요.</p>
                      )}
                    </section>
                  )}
                  {detail.retuningSignal && (
                    <section className="retuning" aria-label="재튜닝 추천">
                      <h3>{detail.retuningSignal.recommended ? '재튜닝 제안' : '재튜닝 신호'}</h3>
                      {detail.retuningSignal.reasons.length ? (
                        <ul aria-label="재튜닝 근거">
                          {detail.retuningSignal.reasons.map((reason, index) => (
                            <li key={`${reason}-${index}`}>{reason}</li>
                          ))}
                        </ul>
                      ) : (
                        <p>아직 재튜닝을 판단할 관찰 근거가 충분하지 않아요.</p>
                      )}
                      <p className="retune-observed">
                        관찰된 피드백: 부정 {detail.retuningSignal.negativeCount}건
                        {detail.retuningSignal.threshold
                          ? detail.retuningSignal.thresholdKind === 'WEIGHTED_NEGATIVE_FEEDBACK'
                            ? ` · 권장 기준 가중치 ${detail.retuningSignal.threshold}`
                            : ` · 권장 기준 ${detail.retuningSignal.threshold}건`
                          : ''}
                        {detail.retuningSignal.feedbackTotal !== undefined
                          ? ` · 전체 ${detail.retuningSignal.feedbackTotal}건`
                          : ''}
                        {detail.retuningSignal.positiveCount !== undefined
                          ? ` · 긍정 ${detail.retuningSignal.positiveCount}건`
                          : ''}
                      </p>
                      {detail.retuningSignal.comparison && (
                        <div className="retune-comparison" aria-label="재튜닝 전후 비교 상태">
                          <div>
                            <strong>전 · {detail.retuningSignal.comparison.beforeLabel}</strong>
                            <span>
                              {retuningQualityCopy(detail.retuningSignal.comparison.beforeQuality)}
                            </span>
                          </div>
                          <div>
                            <strong>후 · {detail.retuningSignal.comparison.afterLabel}</strong>
                            <span>
                              {retuningQualityCopy(detail.retuningSignal.comparison.afterQuality)}
                              {detail.retuningSignal.comparison.outcomeArtifactId
                                ? ' · 결과 기록됨'
                                : ''}
                            </span>
                          </div>
                        </div>
                      )}
                      {detail.retuningSignal.recommended &&
                        detail.retuningSignal.action === 'START_RETUNE' && (
                          <>
                            <p>선택한 문서를 새 후보로 비교합니다. 시작은 직접 선택해야 해요.</p>
                            <Button onClick={() => void startRetune()} disabled={retuneStarting}>
                              {retuneStarting ? '재튜닝 준비 중…' : '재튜닝 시작'}
                            </Button>
                          </>
                        )}
                      {!detail.retuningSignal.recommended && (
                        <p>현재 관찰된 피드백만으로는 재튜닝을 권장하지 않아요.</p>
                      )}
                      {retuneError && <p role="alert">{retuneError}</p>}
                    </section>
                  )}
                  <dl className="spec">
                    <div>
                      <dt>임베딩 모델</dt>
                      <dd>{detail.embeddingModel}</dd>
                    </div>
                    <div>
                      <dt>연결형 질문</dt>
                      <dd>{detail.graphragEnabled ? '사용' : '사용 안 함'}</dd>
                    </div>
                    <div>
                      <dt>검색 방식</dt>
                      <dd>
                        {new Set(readyDocuments.map((document) => document.pipelineLabel)).size > 1
                          ? '일반 검색 (문서별 방식이 다름)'
                          : (readyDocuments[0]?.pipelineLabel ?? '문서 추가 후 비교 필요')}
                      </dd>
                    </div>
                    <div>
                      <dt>실행 상태</dt>
                      <dd>
                        {executionPlan?.ready
                          ? '연결된 모델 서비스 사용'
                          : '개발용 fallback 가능 · 서비스 설정 필요'}
                      </dd>
                    </div>
                  </dl>
                </>
              ) : (
                <div className="manage">
                  <h2>문서 관리</h2>
                  <p>
                    새 문서는 기존 방식을 적용하거나, 별도로 비교해 문서에 맞는 방식을 찾을 수
                    있어요.
                  </p>
                  {reparseNotice && <p role="status">{reparseNotice}</p>}
                  {reparseError && <p role="alert">{reparseError}</p>}
                  {detail.documents.map((document) => (
                    <div className="manage-row" key={document.id}>
                      <div className="manage-row-head">
                        <strong>{document.name}</strong>
                        <Button
                          $variant="danger"
                          onClick={(event) =>
                            openDialog('delete', event.currentTarget, document.id)
                          }
                        >
                          삭제
                        </Button>
                      </div>
                      <dl
                        className="provenance"
                        role="group"
                        aria-label={`${document.name} 출처 및 처리 정보`}
                      >
                        <div>
                          <dt>원본 checksum</dt>
                          <dd>{checksumCopy(document.provenance?.checksum)}</dd>
                        </div>
                        <div>
                          <dt>중복 처리</dt>
                          <dd>{deduplicationCopy(document.provenance?.deduplication)}</dd>
                        </div>
                        <div>
                          <dt>파서</dt>
                          <dd>
                            {document.provenance?.parser
                              ? `${document.provenance.parser}${document.provenance.parserVersion ? ` · ${document.provenance.parserVersion}` : ''}`
                              : '확인할 수 없음'}
                          </dd>
                        </div>
                        <div>
                          <dt>청킹 · 임베딩</dt>
                          <dd>
                            {document.provenance?.chunking ?? '확인할 수 없음'} ·{' '}
                            {document.provenance?.embeddingModel ?? '확인할 수 없음'}
                            {document.provenance?.modelVersion
                              ? ` · ${document.provenance.modelVersion}`
                              : ''}
                          </dd>
                        </div>
                        <div>
                          <dt>원본 보관</dt>
                          <dd>
                            {document.provenance?.originalAvailable === true
                              ? '원본을 다시 읽을 수 있음'
                              : document.provenance?.originalAvailable === false
                                ? '원본을 다시 읽을 수 없음'
                                : '보관 상태를 확인할 수 없음'}
                          </dd>
                        </div>
                        <div>
                          <dt>재파싱 상태</dt>
                          <dd>{reparseStateCopy(document.provenance?.reparse?.state)}</dd>
                        </div>
                      </dl>
                      <p className="provenance-impact">
                        {document.provenance?.reparse?.impact ??
                          '재파싱하면 원본을 다시 읽고 문서 조각과 검색 후보를 새로 준비합니다. 확정된 검색 설정은 다시 비교해야 할 수 있어요.'}
                      </p>
                      {document.provenance?.reparse?.available ? (
                        <Button
                          $variant="secondary"
                          onClick={(event) =>
                            openDialog('reparse', event.currentTarget, document.id)
                          }
                          disabled={Boolean(reparsingDocumentId)}
                        >
                          {reparsingDocumentId === document.id
                            ? '재파싱 시작 중…'
                            : '원본 다시 읽기'}
                        </Button>
                      ) : (
                        <p className="provenance-impact">
                          원본 보관이 확인된 문서에서만 다시 읽기 작업을 시작할 수 있어요.
                        </p>
                      )}
                    </div>
                  ))}
                  <Button
                    $variant="secondary"
                    onClick={(event) => openDialog('add', event.currentTarget)}
                  >
                    문서 추가
                  </Button>
                </div>
              )}
            </div>
          </OutputBody>
        </section>
      </Workspace>
      {dialog && (
        <DialogOverlay
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeDialog();
          }}
        >
          <div
            className="dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="dialog-title"
            ref={dialogRef}
            onKeyDown={trapTab}
          >
            {dialog === 'add' ? (
              <>
                <h2 id="dialog-title">문서를 어떻게 추가할까요?</h2>
                <p>
                  기존 방식을 적용하거나, 이 문서만 따로 비교할 수 있어요. 임베딩 모델은 이 지식
                  공간의 설정을 그대로 사용합니다.
                </p>
                <input
                  aria-label="추가할 문서 선택"
                  type="file"
                  multiple
                  onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
                />
                <div className="choices">
                  <label className="choice">
                    <input type="radio" checked={reuse} onChange={() => setReuse(true)} /> 기존 방식
                    적용 · 바로 준비
                  </label>
                  <label className="choice">
                    <input type="radio" checked={!reuse} onChange={() => setReuse(false)} /> 이 문서
                    따로 비교 · 전체 화면에서 튜닝
                  </label>
                </div>
                {files.length ? (
                  <p>{files.length}개 문서를 준비했어요.</p>
                ) : (
                  <p>먼저 추가할 문서를 선택해 주세요.</p>
                )}
                <div className="actions">
                  <Button $variant="secondary" autoFocus onClick={closeDialog}>
                    취소
                  </Button>
                  <Button onClick={addDocuments} disabled={!files.length || busy}>
                    {reuse ? '추가하고 준비하기' : '비교 시작하기'}
                  </Button>
                </div>
              </>
            ) : dialog === 'reparse' ? (
              <>
                <h2 id="dialog-title">원본을 다시 읽을까요?</h2>
                <p>
                  {detail.documents.find((document) => document.id === targetId)?.name ?? '이 문서'}
                  은(는) 바로 검색 범위에서 제외돼요. 기존 후보와 설정은 기준 기록으로 남고, 완료
                  뒤에는 다시 비교해 주세요.
                </p>
                <div className="actions">
                  <Button $variant="secondary" autoFocus onClick={closeDialog}>
                    취소
                  </Button>
                  <Button
                    onClick={() => {
                      const documentId = targetId;
                      closeDialog();
                      if (documentId) void reparseDocument(documentId);
                    }}
                  >
                    다시 읽기 시작
                  </Button>
                </div>
              </>
            ) : (
              <>
                <h2 id="dialog-title">이 문서를 삭제할까요?</h2>
                <p>문서와 해당 문서의 검색 설정이 함께 제거됩니다. 이 작업은 되돌릴 수 없습니다.</p>
                <div className="actions">
                  <Button $variant="secondary" autoFocus onClick={closeDialog}>
                    취소
                  </Button>
                  <Button $variant="danger" onClick={deleteDocument} disabled={busy}>
                    삭제하기
                  </Button>
                </div>
              </>
            )}
          </div>
        </DialogOverlay>
      )}
    </DetailPage>
  );
}
