import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, vi } from 'vitest';
import { ragApi } from '../../shared/api/client';
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
});
