import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, vi } from 'vitest';
import { ragApi } from '../shared/api/client';
import { RagCreatePage } from './RagCreatePage';

describe('RagCreatePage', () => {
  afterEach(() => vi.restoreAllMocks());
  it('shows several model candidates and selects the recommendation from the answers', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <RagCreatePage />
      </MemoryRouter>,
    );

    await user.click(screen.getByText('네, 중요해요'));
    await user.click(screen.getByRole('button', { name: '후보 비교하기 →' }));

    expect(
      await screen.findByRole('heading', { name: '문서 전체에 사용할 모델을 선택해 주세요.' }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole('radio', { name: /검색|운영/ })).toHaveLength(3);
    expect(screen.getByRole('radio', { name: /Qwen3-Embedding-0.6B/ })).toBeChecked();

    await user.click(screen.getByRole('radio', { name: /BGE-M3/ }));
    expect(screen.getByRole('radio', { name: /BGE-M3/ })).toBeChecked();
  });

  it('shows actual benchmark metrics only when the latest benchmark exists', async () => {
    const user = userEvent.setup();
    vi.spyOn(ragApi, 'recommendEmbeddingModels').mockResolvedValue([
      {
        id: 'BGE-M3',
        label: '균형형 다국어 검색',
        reason: '테스트 추천',
        tradeoff: '테스트 확인 사항',
        recommended: true,
      },
    ]);
    vi.spyOn(ragApi, 'latestEmbeddingBenchmark').mockResolvedValue({
      run: {
        id: 'benchmark-1',
        corpusLabel: '인사 규정 문서',
        queryCount: 24,
        createdAt: '2026-07-31',
      },
      results: [
        {
          modelId: 'BGE-M3',
          recallAt1: 0.75,
          recallAt5: 0.92,
          mrr: 0.81,
          averageLatencyMs: 42,
          dimension: 1024,
          provider: 'local',
          status: 'READY',
        },
      ],
    });
    render(
      <MemoryRouter>
        <RagCreatePage />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole('button', { name: '후보 비교하기 →' }));
    expect(await screen.findByRole('heading', { name: /우리 문서 실측 결과/ })).toBeInTheDocument();
    expect(screen.getByText(/인사 규정 문서 · 질문 24개/)).toBeInTheDocument();
    expect(screen.getByText(/Recall@1 75.0% · Recall@5 92.0%/)).toBeInTheDocument();
    expect(screen.getByText(/MRR 81.0% · 평균 42ms/)).toBeInTheDocument();
  });

  it('keeps the questionnaire available and shows an actionable API error', async () => {
    const user = userEvent.setup();
    vi.spyOn(ragApi, 'recommendEmbeddingModels').mockRejectedValue(
      new Error('추천 서비스를 사용할 수 없어요.'),
    );
    vi.spyOn(ragApi, 'latestEmbeddingBenchmark').mockResolvedValue(undefined);
    render(
      <MemoryRouter>
        <RagCreatePage />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole('button', { name: '후보 비교하기 →' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('추천 서비스를 사용할 수 없어요.');
    expect(screen.getByRole('button', { name: '후보 비교하기 →' })).toBeEnabled();
    expect(screen.getByText('어떤 문서를 다루나요?')).toBeInTheDocument();
  });

  it('opens a plain-language technical explanation from a question-mark label', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <RagCreatePage />
      </MemoryRouter>,
    );

    const help = screen.getByRole('button', { name: '문서 언어 기술 설명' });
    expect(help).toHaveAttribute('aria-expanded', 'false');
    await user.click(help);
    expect(help).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('Multilingual embedding')).toBeVisible();
    expect(screen.getByText(/임베딩 모델의 언어 처리 범위/)).toBeVisible();
  });
});
