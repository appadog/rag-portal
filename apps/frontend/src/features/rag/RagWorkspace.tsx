import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import styled, { css } from 'styled-components';
import { ragApi } from '../../shared/api/client';
import type {
  ChatAnswer,
  ComparisonRound,
  PipelineCandidate,
  RagInstanceDetail,
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

const PageHeader = styled.header`
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
  margin-bottom: 22px;
  h1 {
    margin: 7px 0 5px;
    font-size: 26px;
    letter-spacing: -1px;
  }
  p {
    margin: 0;
    color: ${theme.colors.muted};
    font-size: 14px;
  }
`;
const Drop = styled.label`
  display: grid;
  place-items: center;
  min-height: 245px;
  border: 1.5px dashed ${theme.colors.brand};
  border-radius: ${theme.radius.lg};
  background: ${theme.colors.brandSoft};
  text-align: center;
  padding: 28px;
  cursor: pointer;
  input {
    display: none;
  }
  strong {
    font-size: 18px;
    margin: 10px 0 6px;
  }
  span {
    font-size: 13px;
    color: ${theme.colors.muted};
    line-height: 1.6;
  }
`;
const Progress = styled(Card)`
  padding: 25px;
  .file {
    font-weight: 750;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    margin-bottom: 22px;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 0;
    font-size: 14px;
  }
  .done {
    color: ${theme.colors.brand};
  }
  .doing {
    color: ${theme.colors.progress};
    font-weight: 700;
  }
  .bar {
    height: 7px;
    border-radius: 999px;
    background: ${theme.colors.surfaceMuted};
    overflow: hidden;
    margin: 12px 0 5px;
  }
  .fill {
    height: 100%;
    background: ${theme.colors.progress};
    transition: width 0.4s;
  }
`;
const CompareGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  gap: var(--rp-panel-gap);
  @media (max-width: 60rem) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  @media (max-width: 47.9375rem) {
    grid-template-columns: minmax(0, 1fr);
  }
`;
const CompareControls = styled.div`
  display: flex;
  gap: var(--rp-space-3);
  margin: 0 0 var(--rp-space-5);
  align-items: stretch;
  input {
    min-width: 0;
  }
  @media (max-width: 47.9375rem) {
    flex-direction: column;
    button {
      width: 100%;
    }
  }
`;
const CandidateSwitcher = styled.div`
  display: none;
  gap: var(--rp-space-2);
  overflow-x: auto;
  margin: 0 0 var(--rp-space-4);
  padding-bottom: var(--rp-space-1);
  button {
    flex: 0 0 auto;
    min-height: var(--rp-touch-target);
    padding: 0 var(--rp-space-3);
    border: 1px solid ${theme.colors.line};
    border-radius: ${theme.radius.pill};
    background: ${theme.colors.surface};
    color: ${theme.colors.muted};
    font-size: var(--rp-font-size-13);
    font-weight: var(--rp-weight-semibold);
  }
  button[aria-pressed='true'] {
    border-color: ${theme.colors.brand};
    background: ${theme.colors.brandSoft};
    color: ${theme.colors.brand};
  }
  @media (max-width: 47.9375rem) {
    display: flex;
  }
`;
const CandidateCard = styled(Card)<{ $selected: boolean }>`
  padding: 17px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  border-color: ${({ $selected }) => ($selected ? theme.colors.brand : theme.colors.line)};
  box-shadow: ${({ $selected }) =>
    $selected ? '0 0 0 2px var(--rp-surface-selected)' : theme.shadow};
  .candidate-header {
    display: flex;
    gap: 10px;
    align-items: flex-start;
  }
  .candidate-header input {
    width: 18px;
    height: 18px;
    margin: 2px 0 0;
    accent-color: ${theme.colors.brand};
  }
  h3 {
    font-size: 15px;
    margin: 0 0 4px;
    letter-spacing: -0.25px;
  }
  .meta {
    font-size: 12px;
    color: ${theme.colors.muted};
  }
  .answer {
    font-size: 14px;
    line-height: 1.7;
    margin: 0;
    min-height: 92px;
  }
  .empty-answer {
    padding: 12px;
    border-radius: ${theme.radius.sm};
    background: ${theme.colors.warningSoft};
    color: ${theme.colors.warning};
    font-size: 13px;
    line-height: 1.6;
  }
  .bottom {
    margin-top: auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    color: ${theme.colors.muted};
    font-size: 12px;
  }
  .help {
    border: 0;
    background: transparent;
    color: ${theme.colors.progress};
    text-decoration: underline;
    padding: 0;
    font-size: 12px;
  }
`;
const Citation = styled.button`
  border: 1px solid var(--rp-border-focus);
  background: ${theme.colors.progressSoft};
  color: ${theme.colors.progress};
  border-radius: 999px;
  min-width: 22px;
  min-height: 22px;
  font-weight: 800;
  font-size: 11px;
  vertical-align: middle;
  margin-left: 3px;
  &:focus-visible {
    outline: 0;
    box-shadow: var(--rp-focus-ring);
  }
`;
const Bar = styled.div`
  position: sticky;
  bottom: 16px;
  margin-top: 18px;
  padding: 13px 14px;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(8px);
  border: 1px solid ${theme.colors.line};
  border-radius: ${theme.radius.md};
  box-shadow: ${theme.shadow};
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  @media (max-width: 47.9375rem) {
    bottom: var(--rp-space-2);
    flex-direction: column;
    align-items: stretch;
    .bar-actions {
      display: grid !important;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .bar-actions button {
      min-width: 0;
    }
  }
`;
const Side = styled.aside`
  border-right: 1px solid ${theme.colors.line};
  padding-right: 18px;
  min-height: 600px;
  .label {
    font-size: 12px;
    color: ${theme.colors.muted};
    font-weight: 750;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 10px;
  }
  .doc {
    width: 100%;
    display: flex;
    gap: 9px;
    text-align: left;
    padding: 10px 6px;
    border: 0;
    border-radius: ${theme.radius.sm};
    background: transparent;
    align-items: flex-start;
  }
  .doc:hover {
    background: ${theme.colors.surfaceMuted};
  }
  .doc span {
    font-size: 13px;
    font-weight: 700;
  }
  .doc small {
    display: block;
    margin-top: 3px;
    color: ${theme.colors.muted};
    font-size: 11px;
  }
  .add {
    margin-top: 16px;
    width: 100%;
  }
`;
const DetailGrid = styled.div`
  display: grid;
  grid-template-columns: 255px minmax(0, 1fr);
  gap: 24px;
`;
const Tabs = styled.div`
  border-bottom: 1px solid ${theme.colors.line};
  display: flex;
  gap: 6px;
  margin-bottom: 20px;
  button {
    border: 0;
    background: transparent;
    padding: 10px 12px;
    color: ${theme.colors.muted};
    font-weight: 750;
    border-bottom: 2px solid transparent;
  }
  .active {
    color: ${theme.colors.brand};
    border-color: ${theme.colors.brand};
  }
`;
const Chat = styled(Card)`
  padding: 22px;
  min-height: 430px;
  display: flex;
  flex-direction: column;
  .message {
    background: ${theme.colors.surfaceMuted};
    padding: 15px;
    border-radius: ${theme.radius.md};
    font-size: 14px;
    line-height: 1.75;
    align-self: flex-start;
    max-width: 82%;
  }
  .ask {
    background: ${theme.colors.brand};
    color: white;
    align-self: flex-end;
  }
  .controls {
    display: flex;
    gap: 9px;
    margin-top: auto;
    padding-top: 22px;
  }
  .controls button {
    min-width: 64px;
  }
  .sens {
    display: flex;
    gap: 4px;
    align-items: center;
    margin: 10px 0;
    font-size: 12px;
    color: ${theme.colors.muted};
    button {
      padding: 5px 8px;
      border: 1px solid ${theme.colors.line};
      background: white;
      border-radius: 999px;
      font-size: 12px;
    }
    .selected {
      background: ${theme.colors.brandSoft};
      border-color: ${theme.colors.brand};
      color: ${theme.colors.brand};
      font-weight: 700;
    }
  }
`;
const Evidence = styled.aside`
  position: fixed;
  z-index: 4;
  right: 28px;
  top: 70px;
  width: 370px;
  padding: 20px;
  border: 1px solid ${theme.colors.progress};
  background: white;
  border-radius: ${theme.radius.md};
  box-shadow: ${theme.shadow};
  h3 {
    font-size: 15px;
    margin: 0 0 8px;
  }
  p {
    font-size: 14px;
    line-height: 1.7;
    background: ${theme.colors.progressSoft};
    padding: 12px;
    border-radius: ${theme.radius.sm};
  }
  @media (max-width: 47.9375rem) {
    inset: auto var(--rp-space-2) var(--rp-space-2);
    width: auto;
    max-height: min(70dvh, 38rem);
    overflow-y: auto;
  }
`;
const Confirm = styled.div`
  position: fixed;
  z-index: 8;
  inset: 0;
  background: rgba(20, 25, 30, 0.36);
  display: grid;
  place-items: center;
  .dialog {
    width: min(570px, calc(100vw - 40px));
    padding: 28px;
    background: white;
    border-radius: ${theme.radius.lg};
    box-shadow: ${theme.shadow};
    h2 {
      margin-top: 5px;
    }
    .recap {
      padding: 14px;
      background: ${theme.colors.surfaceMuted};
      border-radius: ${theme.radius.sm};
      font-size: 14px;
      line-height: 1.6;
    }
    .actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 24px;
    }
    @media (max-width: 47.9375rem) {
      width: calc(100vw - var(--rp-space-4));
      padding: var(--rp-space-5);
      .actions {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
  }
`;
const LiveUpdate = styled.p`
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
`;

function CitationChip({
  candidate,
  onOpen,
}: {
  candidate: PipelineCandidate;
  onOpen: (candidate: PipelineCandidate, trigger: HTMLElement) => void;
}) {
  if (!candidate.evidence.length) return null;
  return (
    <Citation
      type="button"
      title={`${candidate.evidence[0].title}: ${candidate.evidence[0].excerpt}`}
      onClick={(event) => onOpen(candidate, event.currentTarget)}
      aria-label={`${candidate.evidence[0].title} 근거 열기`}
    >
      1
    </Citation>
  );
}
function Candidate({
  candidate,
  selected,
  onSelect,
  onOpen,
}: {
  candidate: PipelineCandidate;
  selected: boolean;
  onSelect: () => void;
  onOpen: (candidate: PipelineCandidate, trigger: HTMLElement) => void;
}) {
  const noEvidence = candidate.evidence.length === 0;
  return (
    <CandidateCard $selected={selected}>
      <div className="candidate-header">
        <input
          type="checkbox"
          checked={selected}
          onChange={onSelect}
          aria-label={`${candidate.label}, 현재 ${candidate.selectionCount}회 선택`}
        />
        <div>
          <h3>
            {candidate.label}{' '}
            <button
              className="help"
              title={candidate.description}
              aria-label={`${candidate.label} 설명`}
            >
              ?
            </button>
          </h3>
          <span className="meta">
            선택 {candidate.selectionCount}회
            {candidate.chunkCount ? ` · 근거 조각 ${candidate.chunkCount}개` : ''}
          </span>
        </div>
      </div>
      {noEvidence ? (
        <div className="empty-answer">이 문서 범위에서는 답을 뒷받침할 근거를 찾지 못했어요.</div>
      ) : (
        <p className="answer">
          {candidate.answer}
          <CitationChip candidate={candidate} onOpen={onOpen} />
        </p>
      )}
      {candidate.runtime?.fallback && (
        <div className="empty-answer" role="status">
          개발용 fallback 검색 · {candidate.runtime.warning ?? candidate.runtime.provider}
        </div>
      )}
      <div className="bottom">
        {noEvidence ? (
          <span>원본 조각 없음</span>
        ) : (
          <button
            type="button"
            className="help"
            onClick={(event) => onOpen(candidate, event.currentTarget)}
          >
            원본 조각만 보기
          </button>
        )}
        <span>응답 {(candidate.latencyMs / 1000).toFixed(1)}초</span>
      </div>
    </CandidateCard>
  );
}

function trapSetupDialog(event: ReactKeyboardEvent<HTMLElement>) {
  if (event.key !== 'Tab') return;
  const items = Array.from(
    event.currentTarget.querySelectorAll<HTMLElement>(
      'button:not(:disabled), input:not(:disabled), [tabindex]:not([tabindex="-1"])',
    ),
  );
  if (!items.length) return;
  const first = items[0];
  const last = items[items.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  }
  if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia(query).matches : false,
  );
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, [query]);
  return matches;
}

export function RagSetupPage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<RagInstanceDetail>();
  const [round, setRound] = useState<ComparisonRound>();
  const [selected, setSelected] = useState<string[]>([]);
  const [activeCandidateId, setActiveCandidateId] = useState<string>();
  const [question, setQuestion] = useState('');
  const [showConfirm, setShowConfirm] = useState(false);
  const [evidence, setEvidence] = useState<PipelineCandidate>();
  const [error, setError] = useState<string>();
  const [compareSubmitting, setCompareSubmitting] = useState(false);
  const [finalizeSubmitting, setFinalizeSubmitting] = useState(false);
  const [compareError, setCompareError] = useState<string>();
  const [finalizeError, setFinalizeError] = useState<string>();
  const evidenceTriggerRef = useRef<HTMLElement | null>(null);
  const confirmTriggerRef = useRef<HTMLElement | null>(null);
  const evidenceDialogRef = useRef<HTMLElement | null>(null);
  const confirmDialogRef = useRef<HTMLDivElement | null>(null);
  const singleCandidateMode = useMediaQuery('(max-width: 47.9375rem)');
  useEffect(() => {
    let cancelled = false;
    const sync = async () => {
      try {
        const item = await ragApi.get(id);
        if (cancelled) return;
        setDetail(item);
        if (item.lastRound) {
          setRound(item.lastRound);
          return;
        }
        if (item.status === 'TUNING' && item.documents.length && item.candidates.length)
          setRound(
            await ragApi.compare(
              id,
              '이 문서에서 가장 중요한 내용을 알려줘.',
              item.documents.map((document) => document.id),
            ),
          );
      } catch (err) {
        if (!cancelled) setError((err as Error).message);
      }
    };
    void sync();
    const jobState = detail?.latestJob?.state;
    const timer =
      jobState && !['SUCCEEDED', 'FAILED', 'CANCELLED'].includes(jobState)
        ? window.setInterval(() => void sync(), 2000)
        : undefined;
    return () => {
      cancelled = true;
      if (timer) window.clearInterval(timer);
    };
  }, [id, detail?.latestJob?.state]);
  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    const result = await ragApi.upload(id, [...files]);
    setDetail(result);
    setRound(undefined);
  };
  const cancelPreparation = async () => {
    if (!detail?.latestJob) return;
    await ragApi.cancelJob(detail.latestJob.id);
    setDetail(await ragApi.get(id));
  };
  const retryPreparation = async () => {
    if (!detail?.latestJob) return;
    await ragApi.retryJob(detail.latestJob.id);
    setDetail(await ragApi.get(id));
  };
  const toggle = (candidateId: string) =>
    setSelected((items) =>
      items.includes(candidateId)
        ? items.filter((item) => item !== candidateId)
        : [...items, candidateId],
    );
  const counts = useMemo(
    () =>
      (round?.candidates ?? []).map((candidate) => ({
        ...candidate,
        selectionCount: candidate.selectionCount + (selected.includes(candidate.id) ? 1 : 0),
      })),
    [round, selected],
  );
  useEffect(() => {
    setActiveCandidateId((current) => {
      if (current && round?.candidates.some((candidate) => candidate.id === current))
        return current;
      return round?.candidates[0]?.id;
    });
  }, [round?.id]);
  const visibleCandidates = useMemo(() => {
    if (!singleCandidateMode) return counts;
    const current = activeCandidateId ?? counts[0]?.id;
    return counts.filter((candidate) => candidate.id === current);
  }, [activeCandidateId, counts, singleCandidateMode]);
  const winner = useMemo(() => {
    const sorted = [...counts].sort((a, b) => b.selectionCount - a.selectionCount);
    return sorted[0] &&
      sorted[0].selectionCount > 0 &&
      sorted[0].selectionCount > (sorted[1]?.selectionCount ?? -1)
      ? sorted[0]
      : undefined;
  }, [counts]);
  const nextRound = async () => {
    if (!round || !detail || compareSubmitting) return;
    setCompareSubmitting(true);
    setCompareError(undefined);
    try {
      if (selected.length) await ragApi.vote(round.id, selected);
      const next = await ragApi.compare(
        id,
        question || round.question,
        detail.documents.map((document) => document.id),
      );
      setRound(next);
      setSelected([]);
      setQuestion('');
    } catch (item) {
      setCompareError((item as Error).message);
    } finally {
      setCompareSubmitting(false);
    }
  };
  const finalize = async () => {
    if (!winner || !round || !detail || finalizeSubmitting) return;
    setFinalizeSubmitting(true);
    setFinalizeError(undefined);
    try {
      if (selected.length) await ragApi.vote(round.id, selected);
      await ragApi.finalize(id, detail.documents[0].id);
      navigate(`/rag/${id}`);
    } catch (item) {
      setFinalizeError((item as Error).message);
    } finally {
      setFinalizeSubmitting(false);
    }
  };
  const closeEvidence = () => {
    setEvidence(undefined);
    window.setTimeout(() => evidenceTriggerRef.current?.focus(), 0);
  };
  const closeConfirm = () => {
    setShowConfirm(false);
    window.setTimeout(() => confirmTriggerRef.current?.focus(), 0);
  };
  useEffect(() => {
    if (evidence)
      window.setTimeout(
        () => evidenceDialogRef.current?.querySelector<HTMLElement>('button')?.focus(),
        0,
      );
    if (showConfirm)
      window.setTimeout(
        () => confirmDialogRef.current?.querySelector<HTMLElement>('button')?.focus(),
        0,
      );
  }, [evidence, showConfirm]);
  useEffect(() => {
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        if (showConfirm) closeConfirm();
        else if (evidence) closeEvidence();
      }
    };
    window.addEventListener('keydown', onEscape);
    return () => window.removeEventListener('keydown', onEscape);
  }, [evidence, showConfirm]);
  if (error) return <ErrorState message={error} />;
  if (!detail) return <LoadingState />;
  const isPreparing =
    Boolean(detail.latestJob) &&
    !['SUCCEEDED', 'FAILED', 'CANCELLED'].includes(detail.latestJob?.state ?? 'SUCCEEDED');
  if (!round && isPreparing)
    return (
      <>
        <PageHeader>
          <div>
            <Pill $tone="warning">문서 준비 중</Pill>
            <h1>{detail.name}</h1>
            <p>다른 작업을 해도 괜찮아요. 준비가 끝나면 비교 화면으로 이어집니다.</p>
          </div>
          <Button $variant="secondary" onClick={() => navigate('/rag')}>
            대시보드로
          </Button>
        </PageHeader>
        <Progress>
          <LiveUpdate role="status" aria-live="polite">
            {detail.latestJob?.currentStep} · {detail.latestJob?.completed}/
            {detail.latestJob?.total} 단계 완료
          </LiveUpdate>
          <div className="file">{detail.documents.map((document) => document.name).join(', ')}</div>
          {detail.latestJob?.stages.map((stage) => (
            <div className="row" key={stage.key}>
              <span className={stage.state === 'SUCCEEDED' ? 'done' : 'doing'}>
                {stage.state === 'SUCCEEDED' ? '✓' : '◐'}
              </span>
              <span>{stage.label}</span>
            </div>
          ))}
          <div className="bar">
            <div
              className="fill"
              style={{
                width: `${((detail.latestJob?.completed ?? 0) / (detail.latestJob?.total || 1)) * 100}%`,
              }}
            />
          </div>
          <small>
            {detail.latestJob?.currentStep} · {detail.latestJob?.completed}/
            {detail.latestJob?.total} 단계 완료
          </small>
          {detail.latestJob?.canCancel && (
            <div style={{ marginTop: 16 }}>
              <Button $variant="secondary" onClick={() => void cancelPreparation()}>
                준비 중단
              </Button>
            </div>
          )}
        </Progress>
      </>
    );
  if (!round && detail.latestJob?.state && ['FAILED', 'CANCELLED'].includes(detail.latestJob.state))
    return (
      <>
        <PageHeader>
          <div>
            <Pill $tone="warning">
              문서 준비 {detail.latestJob.state === 'FAILED' ? '실패' : '중단'}
            </Pill>
            <h1>{detail.name}</h1>
            <p>{detail.latestJob.errorMessage ?? detail.latestJob.currentStep}</p>
          </div>
          <Button $variant="secondary" onClick={() => navigate('/rag')}>
            대시보드로
          </Button>
        </PageHeader>
        <Card style={{ padding: 20 }}>
          <p style={{ marginTop: 0, color: theme.colors.muted }}>
            원본 문서와 선택한 모델 설정은 유지됩니다. 준비 작업만 다시 시도할 수 있어요.
          </p>
          <Button onClick={() => void retryPreparation()} disabled={!detail.latestJob.canRetry}>
            문서 준비 다시 시도
          </Button>
        </Card>
      </>
    );
  if (!round)
    return (
      <>
        <PageHeader>
          <div>
            <Pill $tone="brand">문서 준비</Pill>
            <h1>{detail.name}</h1>
            <p>문서를 올리면 비교에 필요한 준비를 자동으로 시작해요.</p>
          </div>
          <Button $variant="secondary" onClick={() => navigate('/rag')}>
            대시보드로
          </Button>
        </PageHeader>
        <Drop>
          <input
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.csv,.xlsx"
            onChange={(event) => upload(event.target.files)}
          />
          <div style={{ fontSize: 32 }}>⌁</div>
          <strong>문서를 드래그하거나 클릭해서 올리세요</strong>
          <span>PDF, DOCX, TXT, CSV, XLSX · 업로드 후 파싱과 비교 준비가 자동으로 시작됩니다.</span>
        </Drop>
      </>
    );
  return (
    <>
      <PageHeader>
        <div>
          <Pill $tone="warning">튜닝 중 · 현재 라운드 {round.id.replace(/^.*?(\d+)$/, '$1')}</Pill>
          <h1>답변과 근거를 비교해 주세요.</h1>
          <p>
            후보 {counts.length}개를 비교 중이에요. 가장 도움이 되는 결과를 하나 이상 고르면, 선택
            횟수가 쌓여요.
          </p>
        </div>
        <Button $variant="secondary" onClick={() => navigate('/rag')}>
          대시보드로
        </Button>
      </PageHeader>
      <CompareControls>
        <Input
          aria-label="비교할 질문"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={round.question}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.nativeEvent.isComposing) void nextRound();
          }}
        />
        <Button onClick={() => void nextRound()} disabled={compareSubmitting}>
          {compareSubmitting ? '비교 중…' : '비교하기'}
        </Button>
      </CompareControls>
      {compareError && (
        <Card role="alert" style={{ padding: 16, marginBottom: 16 }}>
          <p>{compareError}</p>
          <Button $variant="secondary" onClick={() => void nextRound()}>
            같은 조건으로 다시 시도
          </Button>
        </Card>
      )}
      <CandidateSwitcher aria-label="비교 후보 전환">
        {counts.map((candidate, index) => (
          <button
            type="button"
            key={candidate.id}
            aria-pressed={(activeCandidateId ?? counts[0]?.id) === candidate.id}
            onClick={() => setActiveCandidateId(candidate.id)}
          >
            후보 {index + 1}: {candidate.plainLabel}
            {selected.includes(candidate.id) ? ' · 선택됨' : ''}
          </button>
        ))}
      </CandidateSwitcher>
      <CompareGrid>
        {visibleCandidates.map((candidate) => (
          <Candidate
            key={candidate.id}
            candidate={candidate}
            selected={selected.includes(candidate.id)}
            onSelect={() => toggle(candidate.id)}
            onOpen={(candidate, trigger) => {
              evidenceTriggerRef.current = trigger;
              setEvidence(candidate);
            }}
          />
        ))}
      </CompareGrid>
      <Bar>
        <div>
          <strong style={{ fontSize: 13 }}>현재 {selected.length}개 선택</strong>
          <div id="tie-help" style={{ fontSize: 12, color: theme.colors.muted, marginTop: 3 }}>
            {winner
              ? `${winner.label} 조합이 단독 1위예요.`
              : '아직 한 가지 방식이 앞서지 않았어요. 다음 질문에서도 비교해 주세요.'}
          </div>
        </div>
        <div className="bar-actions" style={{ display: 'flex', gap: 8 }}>
          <Button
            $variant="secondary"
            onClick={() => void nextRound()}
            disabled={compareSubmitting}
          >
            {compareSubmitting ? '비교 중…' : '다음 라운드 진행'}
          </Button>
          <Button
            disabled={!winner}
            aria-describedby="tie-help"
            onClick={(event) => {
              confirmTriggerRef.current = event.currentTarget;
              setShowConfirm(true);
            }}
          >
            완료{winner ? ` (${winner.plainLabel})` : ''}
          </Button>
        </div>
      </Bar>
      {evidence && (
        <Evidence
          role="dialog"
          aria-modal="true"
          aria-label="원본 근거"
          ref={evidenceDialogRef}
          onKeyDown={trapSetupDialog}
        >
          <Button $variant="ghost" style={{ float: 'right' }} onClick={closeEvidence}>
            닫기
          </Button>
          <Pill $tone="brand">{evidence.evidence[0]?.page}</Pill>
          <h3>{evidence.evidence[0]?.title}</h3>
          <p>{evidence.evidence[0]?.excerpt}</p>
        </Evidence>
      )}
      {showConfirm && winner && (
        <Confirm role="presentation">
          <div
            className="dialog"
            role="dialog"
            aria-modal="true"
            aria-label="확정 확인"
            ref={confirmDialogRef}
            onKeyDown={trapSetupDialog}
          >
            <Pill $tone="warning">최종 확인</Pill>
            <h2>이 방식으로 확정할까요?</h2>
            <p style={{ color: theme.colors.muted }}>
              다른 비교 결과는 정리되고, 이 문서에는 아래 방식이 기록됩니다.
            </p>
            <div className="recap">
              <strong>{winner.label}</strong>
              <br />
              마지막 질문: {round.question}
              <br />
              답변: {winner.answer}
            </div>
            <div className="actions">
              <Button
                $variant="secondary"
                autoFocus
                onClick={closeConfirm}
                disabled={finalizeSubmitting}
              >
                다시 비교하기
              </Button>
              <Button onClick={() => void finalize()} disabled={finalizeSubmitting}>
                {finalizeSubmitting ? '확정 중…' : '확정하기'}
              </Button>
            </div>
            {finalizeError && (
              <p role="alert">
                {finalizeError}{' '}
                <Button $variant="ghost" onClick={() => void finalize()}>
                  다시 시도
                </Button>
              </p>
            )}
          </div>
        </Confirm>
      )}
    </>
  );
}

function LegacyRagDetailPage() {
  const { id = '' } = useParams();
  const [detail, setDetail] = useState<RagInstanceDetail>();
  const [tab, setTab] = useState<'search' | 'spec'>('search');
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState<ChatAnswer>();
  const [sensitivity, setSensitivity] = useState('평이하게');
  const [evidence, setEvidence] = useState<PipelineCandidate>();
  const [feedback, setFeedback] = useState<number>();
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    ragApi.get(id).then((item) => {
      setDetail(item);
      setSelectedDocs(item.documents.map((doc) => doc.id));
    });
  }, [id]);
  if (!detail) return <LoadingState />;
  const differentPipelines = new Set(detail.documents.map((doc) => doc.pipelineId)).size > 1;
  const ask = async () => {
    if (!question.trim() || !selectedDocs.length) return;
    setFeedback(undefined);
    setAnswer(
      await ragApi.answer(
        id,
        question,
        selectedDocs,
        sensitivity === '유연하게'
          ? 'flexible'
          : sensitivity === '엄격하게'
            ? 'strict'
            : 'balanced',
      ),
    );
  };
  const leaveFeedback = async (rating: 1 | -1) => {
    setFeedback(rating);
    await ragApi.feedback(id, rating);
  };
  return (
    <>
      <PageHeader>
        <div>
          <StatusBadge status={detail.status} />
          <h1>{detail.name}</h1>
          <p>확정된 문서 범위에서 근거와 함께 답을 찾아드려요.</p>
        </div>
      </PageHeader>
      <DetailGrid>
        <Side>
          <div className="label">문서 · 검색 범위</div>
          {detail.documents.map((doc) => (
            <button
              className="doc"
              key={doc.id}
              onClick={() =>
                setSelectedDocs((ids) =>
                  ids.includes(doc.id) ? ids.filter((item) => item !== doc.id) : [...ids, doc.id],
                )
              }
            >
              <input
                aria-label={`${doc.name} 검색에 포함`}
                type="checkbox"
                checked={selectedDocs.includes(doc.id)}
                onChange={() => undefined}
              />
              <div>
                <span>{doc.name}</span>
                <small>{doc.pipelineLabel ?? '비교 준비 중'}</small>
              </div>
            </button>
          ))}
          <Button
            className="add"
            $variant="secondary"
            onClick={() =>
              window.alert(
                '문서 추가 흐름은 다음 단계에서 기존 방식 적용 또는 별도 비교를 선택하도록 연결됩니다.',
              )
            }
          >
            + 문서 추가
          </Button>
        </Side>
        <div>
          <Tabs>
            <button className={tab === 'search' ? 'active' : ''} onClick={() => setTab('search')}>
              검색
            </button>
            <button className={tab === 'spec' ? 'active' : ''} onClick={() => setTab('spec')}>
              설정 스펙
            </button>
          </Tabs>
          {tab === 'spec' ? (
            <Card style={{ padding: 24 }}>
              <h2 style={{ marginTop: 0 }}>읽기 전용 설정</h2>
              <dl
                style={{
                  display: 'grid',
                  gridTemplateColumns: '150px 1fr',
                  gap: '14px 20px',
                  fontSize: 14,
                }}
              >
                <dt style={{ color: theme.colors.muted }}>임베딩 모델</dt>
                <dd style={{ margin: 0 }}>{detail.embeddingModel}</dd>
                <dt style={{ color: theme.colors.muted }}>연결형 질문</dt>
                <dd style={{ margin: 0 }}>{detail.graphragEnabled ? '사용' : '사용 안 함'}</dd>
                <dt style={{ color: theme.colors.muted }}>문서별 확정 방식</dt>
                <dd style={{ margin: 0 }}>
                  {detail.documents.map((doc) => (
                    <div key={doc.id}>
                      {doc.name} · {doc.pipelineLabel ?? '아직 확정 전'}
                    </div>
                  ))}
                </dd>
              </dl>
            </Card>
          ) : (
            <>
              <Chat>
                <Pill $tone="brand">실사용 검색</Pill>
                {!selectedDocs.length ? (
                  <div className="message" style={{ marginTop: 18 }}>
                    검색할 문서를 하나 이상 선택해 주세요.
                  </div>
                ) : answer ? (
                  <>
                    <div className="message ask" style={{ marginTop: 18 }}>
                      {question}
                    </div>
                    <div className="message" style={{ marginTop: 12 }}>
                      {answer.text}{' '}
                      {answer.citations.length > 0 && (
                        <Citation
                          type="button"
                          onClick={() => setEvidence(detail.candidates[0])}
                          aria-label="답변 근거 열기"
                        >
                          1
                        </Citation>
                      )}
                      <div style={{ fontSize: 11, color: theme.colors.muted, marginTop: 8 }}>
                        응답 {(answer.latencyMs / 1000).toFixed(1)}초 ·{' '}
                        <button
                          style={{
                            border: 0,
                            background: 'transparent',
                            color: feedback === 1 ? theme.colors.brand : theme.colors.muted,
                          }}
                          aria-label="좋아요"
                          onClick={() => leaveFeedback(1)}
                        >
                          👍
                        </button>{' '}
                        <button
                          style={{
                            border: 0,
                            background: 'transparent',
                            color: feedback === -1 ? theme.colors.danger : theme.colors.muted,
                          }}
                          aria-label="도움되지 않음"
                          onClick={() => leaveFeedback(-1)}
                        >
                          👎
                        </button>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="message" style={{ marginTop: 18 }}>
                    문서에 대해 궁금한 점을 물어보세요. 답변마다 근거를 바로 확인할 수 있어요.
                  </div>
                )}
                {differentPipelines && (
                  <div className="sens">
                    <span>
                      검색 방식 <button className="selected">일반 검색</button>
                      <button title="하이브리드+재순위화">정밀 검색 ?</button>
                    </span>
                  </div>
                )}
                <div className="sens" role="group" aria-label="검색 민감도">
                  <span>검색 민감도</span>
                  {['유연하게', '평이하게', '엄격하게'].map((item) => (
                    <button
                      key={item}
                      className={sensitivity === item ? 'selected' : ''}
                      onClick={() => setSensitivity(item)}
                    >
                      {item}
                    </button>
                  ))}
                </div>
                <div className="controls">
                  <Input
                    ref={inputRef}
                    aria-label="검색 질문"
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    onKeyDown={(event) => event.key === 'Enter' && ask()}
                    placeholder="예: 국내 출장 숙박비는 얼마까지 되나요?"
                  />
                  <Button onClick={ask} disabled={!selectedDocs.length}>
                    질문하기
                  </Button>
                </div>
              </Chat>
            </>
          )}
        </div>
      </DetailGrid>
      {evidence && (
        <Evidence role="dialog" aria-label="원본 근거">
          <Button
            $variant="ghost"
            style={{ float: 'right' }}
            onClick={() => setEvidence(undefined)}
          >
            닫기
          </Button>
          <Pill $tone="brand">{evidence.evidence[0]?.page}</Pill>
          <h3>{evidence.evidence[0]?.title}</h3>
          <p>{evidence.evidence[0]?.excerpt}</p>
        </Evidence>
      )}
    </>
  );
}

export { RagDetailPage } from './RagDetailWorkspace';
