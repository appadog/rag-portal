import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, vi } from 'vitest';
import { ragApi } from '../../shared/api/client';
import { mockInstances } from '../../shared/mocks/ragFixtures';
import { RagDetailPage } from './RagDetailWorkspace';

function renderWorkspace() {
  return render(
    <MemoryRouter initialEntries={['/rag/travel']}>
      <Routes>
        <Route path="/rag/:id" element={<RagDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('RagDetailPage workspace', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 });
  });
  afterEach(() => vi.restoreAllMocks());
  it('starts mobile in single Work mode and swaps side panels', async () => {
    const user = userEvent.setup();
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 390 });
    renderWorkspace();
    await screen.findByRole('textbox', { name: '검색 질문' });
    const contextToggle = screen.getByRole('button', { name: '문서 컨텍스트 패널 표시 전환' });
    const outputToggle = screen.getByRole('button', { name: '결과 및 근거 패널 표시 전환' });
    expect(contextToggle).toHaveAttribute('aria-pressed', 'false');
    expect(outputToggle).toHaveAttribute('aria-pressed', 'false');
    await user.click(contextToggle);
    expect(contextToggle).toHaveAttribute('aria-pressed', 'true');
    expect(outputToggle).toHaveAttribute('aria-pressed', 'false');
    await user.click(outputToggle);
    expect(contextToggle).toHaveAttribute('aria-pressed', 'false');
    expect(outputToggle).toHaveAttribute('aria-pressed', 'true');
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1024 });
  });

  it('keeps document selection separate from document management', async () => {
    renderWorkspace();
    expect(
      await screen.findByRole('checkbox', { name: /출장비_지급_규정.pdf/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /출장비_지급_규정.pdf 문서 관리 열기/ }),
    ).toBeInTheDocument();
  });

  it('opens evidence from a citation and restores focus on Escape', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const question = await screen.findByRole('textbox', { name: '검색 질문' });
    await user.type(question, '국내 출장 숙박비는 얼마까지 되나요?');
    await user.click(screen.getByRole('button', { name: '질문하기' }));
    const citation = await screen.findByRole('button', { name: /근거 열기/ });
    await user.click(citation);
    const drawer = await screen.findByRole('complementary', { name: '문서 근거' });
    expect(drawer).toBeInTheDocument();
    await user.keyboard('{Escape}');
    await waitFor(() =>
      expect(screen.queryByRole('complementary', { name: '문서 근거' })).not.toBeInTheDocument(),
    );
    expect(citation).toHaveFocus();
  });

  it('keeps partial-answer context when the user stops a search', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const question = await screen.findByRole('textbox', { name: '검색 질문' });
    await user.type(question, '국내 출장 숙박비는 얼마까지 되나요?');
    await user.click(screen.getByRole('button', { name: '질문하기' }));
    const stop = await screen.findByRole('button', { name: '중단' });
    await user.click(stop);
    expect(await screen.findByText(/답변 생성을 중단했어요/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '질문하기' })).toBeInTheDocument();
  });

  it('explains the selected search sensitivity in plain language', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    await screen.findByRole('textbox', { name: '검색 질문' });
    expect(screen.getByText(/관련성과 범위의 균형/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '엄격하게' }));
    expect(screen.getByText(/문서에 더 직접적으로 적힌 내용/)).toBeInTheDocument();
  });

  it('locks the document scope while a search is in progress and records that request scope', async () => {
    const user = userEvent.setup();
    let resolveSearch:
      | ((answer: Awaited<ReturnType<typeof ragApi.streamAnswer>>) => void)
      | undefined;
    const streamAnswer = vi.spyOn(ragApi, 'streamAnswer').mockImplementation(
      (_id, _question, documentIds, sensitivity) =>
        new Promise((resolve) => {
          expect(documentIds).toEqual(['travel-policy', 'benefits']);
          expect(sensitivity).toBe('balanced');
          resolveSearch = resolve;
        }),
    );
    renderWorkspace();
    const question = await screen.findByRole('textbox', { name: '검색 질문' });
    await user.type(question, '국내 출장 숙박비는 얼마까지 되나요?');
    await user.click(screen.getByRole('button', { name: '질문하기' }));

    const documentToggle = screen.getByRole('checkbox', { name: /출장비_지급_규정.pdf/ });
    expect(documentToggle).toBeDisabled();
    expect(
      await screen.findByText(/검색 범위: 출장비_지급_규정.pdf, 복리후생_안내.pdf · 평이하게/),
    ).toBeInTheDocument();
    expect(streamAnswer).toHaveBeenCalledTimes(1);

    resolveSearch?.({ text: '검색 결과', citations: [], latencyMs: 1 });
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: '중단' })).not.toBeInTheDocument(),
    );
  });

  it('connects Output tabs to a tabpanel and supports roving Arrow navigation', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const settings = await screen.findByRole('tab', { name: '설정' });
    expect(settings).toHaveAttribute('aria-controls', 'rag-travel-output-panel-settings');
    settings.focus();
    await user.keyboard('{ArrowRight}');

    const documents = screen.getByRole('tab', { name: '문서' });
    await waitFor(() => expect(documents).toHaveAttribute('aria-selected', 'true'));
    expect(documents).toHaveFocus();
    expect(screen.getByRole('tabpanel')).toHaveAttribute(
      'aria-labelledby',
      'rag-travel-output-tab-documents',
    );
  });

  it('shows full-document reindex progress without disabling current search', async () => {
    vi.spyOn(ragApi, 'get').mockResolvedValue({
      ...mockInstances[0],
      fullReindexJob: {
        id: 'full-reindex-1',
        state: 'INDEXING',
        currentStep: '전체 문서 조각을 색인하고 있어요',
        completed: 3,
        total: 8,
        canRetry: false,
        canCancel: false,
        stages: [],
      },
    });
    renderWorkspace();

    expect(
      await screen.findByText(
        /전체 문서 색인 중: 전체 문서 조각을 색인하고 있어요 · 3\/8 단계 완료/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: '검색 질문' })).not.toBeDisabled();
  });

  it('shows grounded generation progress and a calm fallback disclosure from stream metadata', async () => {
    const user = userEvent.setup();
    let resolveAnswer:
      | ((answer: Awaited<ReturnType<typeof ragApi.streamAnswer>>) => void)
      | undefined;
    vi.spyOn(ragApi, 'streamAnswer').mockImplementation(
      (_id, _question, _documentIds, _sensitivity, options) => {
        options?.onUpdate?.({
          text: '',
          citations: [],
          generation: { status: 'GENERATING', fallback: false },
        });
        return new Promise((resolve) => {
          resolveAnswer = resolve;
        });
      },
    );
    renderWorkspace();
    const question = await screen.findByRole('textbox', { name: '검색 질문' });
    await user.type(question, '국내 출장 숙박비는 얼마까지 되나요?');
    await user.click(screen.getByRole('button', { name: '질문하기' }));

    await waitFor(() =>
      expect(
        screen.getAllByText(/문서 근거를 바탕으로 답을 정리하고 있어요/).length,
      ).toBeGreaterThan(0),
    );
    resolveAnswer?.({
      text: '근거 기반 답변',
      citations: [],
      latencyMs: 10,
      generation: { fallback: true, detail: '생성 모델을 사용할 수 없었어요.' },
    });
    expect(
      await screen.findByText(
        /문서 근거를 바탕으로 발췌한 결과예요 · 생성 모델을 사용할 수 없었어요/,
      ),
    ).toBeInTheDocument();
  });

  it('discloses multi-document coverage and opens each document source in Evidence', async () => {
    const user = userEvent.setup();
    vi.spyOn(ragApi, 'streamAnswer').mockResolvedValue({
      text: '두 문서의 근거를 함께 정리한 답변',
      citations: [
        {
          id: 'policy-1',
          title: '출장비_지급_규정.pdf',
          documentName: '출장비_지급_규정.pdf',
          excerpt: '숙박비 한도는 1박 10만원입니다.',
          page: 'p. 3',
        },
        {
          id: 'benefits-1',
          title: '복리후생_안내.pdf',
          documentName: '복리후생_안내.pdf',
          excerpt: '복리후생 지급 기준을 안내합니다.',
          page: 'p. 2',
        },
      ],
      latencyMs: 10,
      documentCoverage: [
        { documentName: '출장비_지급_규정.pdf', citationCount: 1 },
        { documentName: '복리후생_안내.pdf', citationCount: 1 },
      ],
    });
    renderWorkspace();
    const question = await screen.findByRole('textbox', { name: '검색 질문' });
    await user.type(question, '숙박비와 복리후생 기준을 알려줘');
    await user.click(screen.getByRole('button', { name: '질문하기' }));

    expect(await screen.findByText('2개 문서의 근거를 함께 확인했어요.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '복리후생_안내.pdf 근거 1개 보기' }));
    expect(await screen.findByRole('heading', { name: '복리후생_안내.pdf' })).toBeInTheDocument();
  });
});
