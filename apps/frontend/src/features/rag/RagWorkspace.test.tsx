import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ragApi } from '../../shared/api/client';
import { candidateFixtures, mockInstances } from '../../shared/mocks/ragFixtures';
import type { RagInstanceDetail } from '../../shared/api/types';
import { RagSetupPage } from './RagWorkspace';

function setupDetail(): RagInstanceDetail {
  const [ready, preparing, failed, noEvidence] = candidateFixtures.map((candidate) => ({
    ...candidate,
  }));
  return {
    ...mockInstances[0],
    status: 'TUNING',
    latestJob: {
      id: 'job-candidates',
      state: 'FAILED',
      currentStep: '후보 준비 일부 실패',
      completed: 2,
      total: 4,
      canRetry: true,
      canCancel: false,
      stages: [],
    },
    lastRound: {
      id: 'round-readiness',
      question: '출장 식비 한도는?',
      candidates: [
        {
          ...ready,
          comparisonState: 'READY',
          generation: { fallback: true, provider: 'extractive' },
        },
        {
          ...preparing,
          comparisonState: 'PREPARING',
          comparisonStateDetail: '색인을 준비하고 있어요.',
        },
        {
          ...failed,
          comparisonState: 'FAILED',
          comparisonStateDetail: '문서 조각을 만들지 못했어요.',
        },
        {
          ...noEvidence,
          comparisonState: 'NO_EVIDENCE',
          comparisonStateDetail: '근거를 찾지 못했어요.',
        },
      ],
    },
  };
}

function renderSetup() {
  return render(
    <MemoryRouter initialEntries={['/rag/travel/setup']}>
      <Routes>
        <Route path="/rag/:id/setup" element={<RagSetupPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('RagSetupPage candidate readiness', () => {
  afterEach(() => vi.restoreAllMocks());

  it('only permits READY candidates to be selected and voted', async () => {
    const user = userEvent.setup();
    const detail = setupDetail();
    vi.spyOn(ragApi, 'get').mockResolvedValue(detail);
    const vote = vi.spyOn(ragApi, 'vote').mockResolvedValue();
    vi.spyOn(ragApi, 'compare').mockResolvedValue(detail.lastRound!);
    renderSetup();

    const ready = await screen.findByRole('checkbox', { name: /일반 검색, 비교 가능/ });
    const preparing = screen.getByRole('checkbox', { name: /정밀 검색, 준비 중/ });
    const failed = screen.getByRole('checkbox', { name: /맥락 검색, 준비 실패/ });
    const noEvidence = screen.getByRole('checkbox', { name: /키워드 검색, 근거 없음/ });
    expect(preparing).toBeDisabled();
    expect(failed).toBeDisabled();
    expect(noEvidence).toBeDisabled();
    expect(screen.getByRole('region', { name: /정밀 검색, 준비 중/ })).toHaveAttribute(
      'aria-busy',
      'true',
    );
    expect(screen.getByText(/준비 중: 색인을 준비하고 있어요/)).toBeInTheDocument();
    expect(screen.getByText(/질문이나 문서 범위를 바꿔 다시 비교/)).toBeInTheDocument();
    expect(screen.getByText('준비됨 1/4 · 이번 라운드 0개 선택')).toBeInTheDocument();
    expect(
      screen.getByText('답변과 근거를 보고 도움이 된 후보를 하나 이상 골라 주세요.'),
    ).toBeInTheDocument();
    expect(screen.getByText('문서 근거 발췌 결과 · extractive')).toBeInTheDocument();

    await user.click(ready);
    await user.click(screen.getByRole('button', { name: '다음 라운드 진행' }));
    await waitFor(() => expect(vote).toHaveBeenCalledWith('round-readiness', ['article-hybrid']));
  });

  it('shows failed-candidate recovery through the existing job retry action', async () => {
    const user = userEvent.setup();
    vi.spyOn(ragApi, 'get').mockResolvedValue(setupDetail());
    const retry = vi.spyOn(ragApi, 'retryJob').mockResolvedValue();
    renderSetup();

    expect(await screen.findByText('문서 조각을 만들지 못했어요.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '문서 준비 다시 시도' }));
    await waitFor(() => expect(retry).toHaveBeenCalledWith('job-candidates'));
  });

  it('explains why completion stays disabled when no candidate is ready', async () => {
    const detail = setupDetail();
    detail.lastRound = {
      ...detail.lastRound!,
      candidates: detail.lastRound!.candidates.map((candidate) => ({
        ...candidate,
        comparisonState: 'PREPARING',
      })),
    };
    vi.spyOn(ragApi, 'get').mockResolvedValue(detail);
    renderSetup();

    expect(await screen.findByText('준비됨 0/4 · 이번 라운드 0개 선택')).toBeInTheDocument();
    expect(screen.getByText('아직 비교할 준비가 된 후보가 없어요.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^완료/ })).toBeDisabled();
  });

  it('explains when a large document uses a sample for comparison', async () => {
    const detail = setupDetail();
    detail.documents = detail.documents.map((document, index) =>
      index === 0
        ? {
            ...document,
            comparisonScope: 'SAMPLE',
            estimatedChunkCount: 1200,
            comparisonChunkCount: 120,
          }
        : document,
    );
    vi.spyOn(ragApi, 'get').mockResolvedValue(detail);
    renderSetup();

    expect(await screen.findByRole('status', { name: '표본 문서 비교 안내' })).toBeInTheDocument();
    expect(screen.getByText(/대표 조각 120\/1200개만 사용했어요/)).toBeInTheDocument();
    expect(screen.getByText(/전체 문서 색인을 이어서 준비합니다/)).toBeInTheDocument();
  });
});
