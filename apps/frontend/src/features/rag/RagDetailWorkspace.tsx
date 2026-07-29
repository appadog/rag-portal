import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import styled, { css } from 'styled-components';
import { ragApi } from '../../shared/api/client';
import type { ChatAnswer, PipelineCandidate, RagInstanceDetail } from '../../shared/api/types';
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
type StreamingAnswer = Pick<ChatAnswer, 'text' | 'citations'> & {
  question: string;
  state: 'streaming' | 'interrupted' | 'failed';
};

const sensitivityDescriptions: Record<string, string> = {
  flexible: '유연하게: 표현이 조금 달라도 관련된 내용을 넓게 찾아봐요.',
  balanced: '평이하게: 관련성과 범위의 균형을 맞춰 답을 찾아요.',
  strict: '엄격하게: 문서에 더 직접적으로 적힌 내용만 우선해요.',
};

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
    min-height: calc(100dvh - 11rem);
    flex: 0 0 auto;
    grid-template-columns: minmax(14rem, 17rem) minmax(0, 1fr);
    .output {
      grid-column: 1/-1;
      min-height: 20rem;
    }
    .output[data-open='false'] {
      display: none;
    }
  }
  @media (max-width: 720px) {
    grid-template-columns: minmax(0, 1fr);
    min-height: auto;
    .context,
    .output {
      grid-column: 1;
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
    display: flex;
    justify-content: space-between;
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
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [answer, setAnswer] = useState<ChatAnswer>();
  const [lastQuestion, setLastQuestion] = useState('');
  const [streamingAnswer, setStreamingAnswer] = useState<StreamingAnswer>();
  const [draft, setDraft] = useState('');
  const [sensitivity, setSensitivity] = useState('balanced');
  const [open, setOpen] = useState<Record<PanelName, boolean>>(() =>
    typeof window !== 'undefined' && window.innerWidth <= 720
      ? { context: false, output: false }
      : { context: true, output: true },
  );
  const [view, setView] = useState<OutputView>('settings');
  const [evidence, setEvidence] = useState<PipelineCandidate>();
  const [dialog, setDialog] = useState<'add' | 'delete' | undefined>();
  const [targetId, setTargetId] = useState<string>();
  const [files, setFiles] = useState<File[]>([]);
  const [reuse, setReuse] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [queryError, setQueryError] = useState<string>();
  const evidenceHeadingRef = useRef<HTMLHeadingElement | null>(null);
  const evidenceTriggerRef = useRef<HTMLButtonElement | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const answerAbortRef = useRef<AbortController>();
  const load = () =>
    ragApi
      .get(id)
      .then((item) => {
        setDetail(item);
        setSelectedIds((prior) =>
          prior.length
            ? prior.filter((value) => item.documents.some((document) => document.id === value))
            : item.documents
                .filter((document) => document.pipelineId)
                .map((document) => document.id),
        );
      })
      .catch((item: Error) => setError(item.message));
  useEffect(() => {
    load();
  }, [id]);
  useEffect(() => {
    if (evidence) {
      setView('evidence');
      window.setTimeout(() => evidenceHeadingRef.current?.focus(), 0);
    }
  }, [evidence]);
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && evidence) {
        setEvidence(undefined);
        evidenceTriggerRef.current?.focus();
      }
      if (event.key === 'Escape' && dialog) setDialog(undefined);
    };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [evidence, dialog]);
  useEffect(() => {
    if (dialog) window.setTimeout(() => focusable(dialogRef.current)?.focus(), 0);
  }, [dialog]);
  useEffect(() => () => answerAbortRef.current?.abort(), []);
  useEffect(() => {
    const jobState = detail?.latestJob?.state;
    if (!jobState || jobState === 'SUCCEEDED' || jobState === 'FAILED') return;
    const timer = window.setInterval(load, 2000);
    return () => window.clearInterval(timer);
  }, [detail?.latestJob?.id, detail?.latestJob?.state]);
  if (error) return <ErrorState message={error} retry={load} />;
  if (!detail) return <LoadingState label="지식 공간과 문서를 불러오고 있어요…" />;
  const toggleDocument = (documentId: string) =>
    setSelectedIds((ids) =>
      ids.includes(documentId) ? ids.filter((item) => item !== documentId) : [...ids, documentId],
    );
  const togglePanel = (panel: PanelName) =>
    setOpen((state) => {
      const nextOpen = !state[panel];
      if (typeof window !== 'undefined' && window.innerWidth <= 720 && nextOpen)
        return panel === 'context'
          ? { context: true, output: false }
          : { context: false, output: true };
      return { ...state, [panel]: nextOpen };
    });
  const showPanel = (panel: PanelName) =>
    setOpen((state) =>
      typeof window !== 'undefined' && window.innerWidth <= 720
        ? panel === 'context'
          ? { context: true, output: false }
          : { context: false, output: true }
        : { ...state, [panel]: true },
    );
  const searchDisabled = selectedIds.length === 0 || !draft.trim() || busy;
  const disabledReason = !selectedIds.length
    ? '먼저 검색할 문서를 하나 이상 선택해 주세요.'
    : !draft.trim()
      ? '질문을 입력하면 검색할 수 있어요.'
      : busy
        ? '답을 찾고 있어요.'
        : '';
  const ask = async (question = draft) => {
    if (searchDisabled) return;
    const controller = new AbortController();
    answerAbortRef.current = controller;
    setBusy(true);
    setQueryError(undefined);
    setStreamingAnswer({ question, text: '', citations: [], state: 'streaming' });
    try {
      const nextAnswer = await ragApi.streamAnswer(id, question, selectedIds, sensitivity, {
        signal: controller.signal,
        onUpdate: (partial) =>
          setStreamingAnswer((current) =>
            current ? { ...current, ...partial, state: 'streaming' } : current,
          ),
      });
      if (controller.signal.aborted) return;
      setAnswer(nextAnswer);
      setLastQuestion(question);
      setStreamingAnswer(undefined);
    } catch (item) {
      if ((item as Error).name === 'AbortError') {
        setStreamingAnswer((current) => (current ? { ...current, state: 'interrupted' } : current));
      } else {
        setQueryError((item as Error).message);
        setStreamingAnswer((current) => (current ? { ...current, state: 'failed' } : current));
      }
    } finally {
      if (answerAbortRef.current === controller) setBusy(false);
    }
  };
  const stopAnswer = () => answerAbortRef.current?.abort();
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
    const navigateUrl = candidate.evidence[0]?.navigateUrl;
    if (navigateUrl) {
      try {
        const source = await ragApi.evidence(navigateUrl);
        setEvidence((current) =>
          current ? { ...current, evidence: [{ ...current.evidence[0], ...source }] } : current,
        );
      } catch (item) {
        setError((item as Error).message);
      }
    }
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
  const readyDocuments = detail.documents.filter((document) => document.pipelineId);
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
        </div>
        <div className="tools">
          <IconButton
            $active={open.context}
            aria-label="문서 컨텍스트 패널 표시 전환"
            aria-pressed={open.context}
            onClick={() => togglePanel('context')}
          >
            문서
          </IconButton>
          <IconButton
            $active={open.output}
            aria-label="결과 및 근거 패널 표시 전환"
            aria-pressed={open.output}
            onClick={() => togglePanel('output')}
          >
            근거
          </IconButton>
        </div>
      </Header>
      <Workspace aria-label="RAG 검색 작업 공간">
        <section className="panel context" data-open={open.context} aria-label="문서 컨텍스트">
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
                    disabled={!document.pipelineId}
                    onChange={() => toggleDocument(document.id)}
                    aria-describedby={`doc-meta-${document.id}`}
                  />
                  <label htmlFor={`doc-${document.id}`}>
                    <strong>{document.name}</strong>
                    <small id={`doc-meta-${document.id}`}>
                      {document.pipelineLabel ?? '아직 비교가 필요해요'}
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
            <Button className="add" $variant="secondary" onClick={() => setDialog('add')}>
              + 문서 추가
            </Button>
          </ContextBody>
        </section>
        <section className="panel work" aria-label="검색 작업">
          <div className="panel-head">
            <span>Work · 검색</span>
            <span role="status" aria-live="polite">
              {busy
                ? '답을 찾고 있어요…'
                : selectedIds.length
                  ? `${selectedIds.length}개 문서 선택됨`
                  : '문서를 선택해 주세요'}
            </span>
          </div>
          <WorkBody>
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
                    {streamingAnswer.text || '문서에서 근거를 확인하고 있어요…'}
                    {streamingAnswer.citations.map(citationButton)}
                    <p className="stream-status" role="status">
                      {streamingAnswer.state === 'streaming'
                        ? '답변을 만드는 중이에요. 필요하면 중단할 수 있어요.'
                        : streamingAnswer.state === 'interrupted'
                          ? '답변 생성을 중단했어요. 지금까지 받은 내용은 남아 있어요.'
                          : '답변 연결이 끊겼어요. 지금까지 받은 내용을 확인하거나 다시 질문해 주세요.'}
                    </p>
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
                  disabled={busy || !readyDocuments.length}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.nativeEvent.isComposing) ask();
                  }}
                  placeholder="예: 국내 출장 숙박비는 얼마까지 되나요?"
                />
                {busy ? (
                  <Button $variant="secondary" onClick={stopAnswer}>
                    중단
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
                <p className="reason" role="alert">
                  {queryError}
                </p>
              )}
              {disabledReason && (
                <p className="reason" id="composer-reason">
                  {disabledReason}
                </p>
              )}
            </div>
          </WorkBody>
        </section>
        <section className="panel output" data-open={open.output} aria-label="결과 및 근거">
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
              <button
                role="tab"
                aria-selected={view === 'evidence'}
                onClick={() => setView('evidence')}
              >
                근거
              </button>
              <button
                role="tab"
                aria-selected={view === 'settings'}
                onClick={() => setView('settings')}
              >
                설정
              </button>
              <button
                role="tab"
                aria-selected={view === 'documents'}
                onClick={() => setView('documents')}
              >
                문서
              </button>
            </div>
            {view === 'evidence' ? (
              evidence ? (
                <>
                  <Pill $tone="brand">{evidence.evidence[0]?.page}</Pill>
                  <h2 ref={evidenceHeadingRef} tabIndex={-1}>
                    {evidence.evidence[0]?.title}
                  </h2>
                  <p className="excerpt">{evidence.evidence[0]?.excerpt}</p>
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
                    답변 속 번호를 누르면 해당 문서 조각이 여기에 열립니다. 근거가 없는 답은 경고로
                    구분됩니다.
                  </p>
                </>
              )
            ) : view === 'settings' ? (
              <>
                <h2>확정된 설정</h2>
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
                </dl>
              </>
            ) : (
              <div className="manage">
                <h2>문서 관리</h2>
                <p>
                  새 문서는 기존 방식을 적용하거나, 별도로 비교해 문서에 맞는 방식을 찾을 수 있어요.
                </p>
                {detail.documents.map((document) => (
                  <div className="manage-row" key={document.id}>
                    <span>{document.name}</span>
                    <Button
                      $variant="danger"
                      onClick={() => {
                        setTargetId(document.id);
                        setDialog('delete');
                      }}
                    >
                      삭제
                    </Button>
                  </div>
                ))}
                <Button $variant="secondary" onClick={() => setDialog('add')}>
                  문서 추가
                </Button>
              </div>
            )}
          </OutputBody>
        </section>
      </Workspace>
      {dialog && (
        <DialogOverlay
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setDialog(undefined);
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
                  <Button $variant="secondary" autoFocus onClick={() => setDialog(undefined)}>
                    취소
                  </Button>
                  <Button onClick={addDocuments} disabled={!files.length || busy}>
                    {reuse ? '추가하고 준비하기' : '비교 시작하기'}
                  </Button>
                </div>
              </>
            ) : (
              <>
                <h2 id="dialog-title">이 문서를 삭제할까요?</h2>
                <p>문서와 해당 문서의 검색 설정이 함께 제거됩니다. 이 작업은 되돌릴 수 없습니다.</p>
                <div className="actions">
                  <Button $variant="secondary" autoFocus onClick={() => setDialog(undefined)}>
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
