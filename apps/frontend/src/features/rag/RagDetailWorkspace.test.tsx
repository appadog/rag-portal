import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, vi } from 'vitest';
import { ragApi, SearchPreflightError } from '../../shared/api/client';
import { mockInstances } from '../../shared/mocks/ragFixtures';
import { RagDetailPage } from './RagDetailWorkspace';

function renderWorkspace() {
  return render(
    <MemoryRouter initialEntries={['/rag/travel']}>
      <Routes>
        <Route path="/rag/:id" element={<RagDetailPage />} />
        <Route path="/rag/:id/setup" element={<div>재튜닝 설정</div>} />
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

  it('keeps Work uncovered by default at tablet widths and permits only one drawer', async () => {
    const user = userEvent.setup();
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1280 });
    renderWorkspace();
    await screen.findByRole('textbox', { name: '검색 질문' });
    const contextToggle = screen.getByRole('button', { name: '문서 컨텍스트 패널 표시 전환' });
    const outputToggle = screen.getByRole('button', { name: '결과 및 근거 패널 표시 전환' });
    expect(contextToggle).toHaveAttribute('aria-pressed', 'true');
    expect(outputToggle).toHaveAttribute('aria-pressed', 'false');

    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 800 });
    act(() => window.dispatchEvent(new Event('resize')));
    await waitFor(() => {
      expect(contextToggle).toHaveAttribute('aria-pressed', 'false');
      expect(outputToggle).toHaveAttribute('aria-pressed', 'false');
    });
    await user.click(contextToggle);
    expect(contextToggle).toHaveAttribute('aria-pressed', 'true');
    expect(outputToggle).toHaveAttribute('aria-pressed', 'false');
    await user.click(outputToggle);
    expect(contextToggle).toHaveAttribute('aria-pressed', 'false');
    expect(outputToggle).toHaveAttribute('aria-pressed', 'true');
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
    const stop = await screen.findByRole('button', { name: '표시 중단' });
    await user.click(stop);
    expect(
      await screen.findByText(/이 화면의 답변 표시를 중단했어요. 서버 작업은 계속될 수 있어요/),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '질문하기' })).toBeInTheDocument();
  });

  it('names the conflicted document and offers scope recovery before a stream opens', async () => {
    const user = userEvent.setup();
    vi.spyOn(ragApi, 'streamAnswer').mockRejectedValue(
      new SearchPreflightError(
        '전체 문서 색인이 끝날 때까지 기다린 뒤 다시 검색해 주세요.',
        ['travel-policy'],
        'FULL_REINDEX_PENDING',
      ),
    );
    renderWorkspace();
    await user.type(await screen.findByRole('textbox', { name: '검색 질문' }), '검색할게요');
    await user.click(screen.getByRole('button', { name: '질문하기' }));

    expect(
      await screen.findByText(
        '출장비_지급_규정.pdf: 전체 문서 색인이 끝날 때까지 기다린 뒤 다시 검색해 주세요.',
      ),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '문서 선택 조정하기' }));
    expect(screen.getByRole('checkbox', { name: /출장비_지급_규정.pdf/ })).toHaveFocus();
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

  it('blocks only a selected document while its full reindex is pending', async () => {
    const user = userEvent.setup();
    vi.spyOn(ragApi, 'get').mockResolvedValue({
      ...mockInstances[0],
      documents: mockInstances[0].documents.map((document, index) =>
        index === 0
          ? {
              ...document,
              fullReindexRequired: true,
              fullReindexReady: false,
              fullReindexState: 'INDEXING',
            }
          : document,
      ),
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
        /전체 문서 색인 중: 전체 문서 조각을 색인하고 있어요 · 3\/8 단계 완료 · 완료 전에는 해당 문서 검색을 잠시 기다려 주세요/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: '검색 질문' })).toBeDisabled();
    expect(screen.getByText(/전체 문서 색인이 완료될 때까지 검색할 수 없어요/)).toBeInTheDocument();
    await user.click(screen.getByRole('checkbox', { name: /출장비_지급_규정.pdf/ }));
    expect(screen.getByRole('textbox', { name: '검색 질문' })).not.toBeDisabled();
  });

  it('shows a compact developer runtime gate without exposing raw service errors', async () => {
    vi.spyOn(ragApi, 'executionPlan').mockResolvedValue({
      embeddingModel: 'BGE-M3',
      ready: false,
      fallbackPolicy: 'connection refused at http://generator.internal',
      requiredServices: [
        {
          key: 'embedding-bge-m3',
          technique: 'embedding',
          modelId: 'BAAI/bge-m3',
          runtime: 'tei',
          status: 'NOT_CONFIGURED',
          ready: false,
          detail: 'RAG_EMBEDDING_URL_BGE_M3 is missing',
        },
        {
          key: 'generator-grounded',
          technique: 'grounded_generation',
          modelId: 'configured-local-generator',
          runtime: 'http',
          status: 'UNAVAILABLE',
          ready: false,
          detail: 'connection refused at http://generator.internal',
        },
      ],
    });
    vi.spyOn(ragApi, 'modelRuntime').mockResolvedValue([]);
    renderWorkspace();

    expect(await screen.findByRole('status', { name: '배포 전 런타임 점검' })).toHaveTextContent(
      '개발자 점검 · 런타임 확인 필요',
    );
    expect(screen.getByText('연결 필요: 임베딩, 근거 기반 생성')).toBeInTheDocument();
    expect(screen.queryByText(/connection refused|RAG_EMBEDDING_URL/)).not.toBeInTheDocument();
  });

  it('shows recoverable job states and recent history without queue internals', async () => {
    const user = userEvent.setup();
    const stalledJob = {
      id: 'job-recovery',
      state: 'FAILED' as const,
      operationalState: 'DEAD_LETTER',
      currentStep: '문서 준비를 다시 시작할 수 있어요.',
      completed: 1,
      total: 3,
      canRetry: true,
      canCancel: false,
      attempt: 2,
      stages: [],
    };
    vi.spyOn(ragApi, 'get').mockResolvedValue({ ...mockInstances[0], latestJob: stalledJob });
    vi.spyOn(ragApi, 'jobs').mockResolvedValue([
      stalledJob,
      {
        id: 'job-recovery-pending',
        state: 'QUEUED',
        operationalState: 'RECOVERY_PENDING',
        currentStep: '복구 준비 중',
        completed: 0,
        total: 3,
        canRetry: false,
        canCancel: false,
        stages: [],
      },
      {
        id: 'job-finished',
        state: 'SUCCEEDED',
        currentStep: '완료',
        completed: 3,
        total: 3,
        canRetry: false,
        canCancel: false,
        stages: [],
      },
    ]);
    const retry = vi.spyOn(ragApi, 'retryJob').mockResolvedValue();
    renderWorkspace();

    const operations = await screen.findByRole('region', { name: '문서 작업 상태' });
    expect(operations).toHaveTextContent('작업이 멈춰 복구 대기 중');
    expect(operations).toHaveTextContent('복구 준비 중');
    expect(operations).toHaveTextContent('준비 완료');
    expect(operations).toHaveTextContent('재시도 2회');
    expect(screen.queryByText(/redis|dead-letter queue|storage_key/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '이 작업 다시 시도' }));
    await waitFor(() => expect(retry).toHaveBeenCalledWith('job-recovery'));
  });

  it('explains a feedback-based retuning recommendation and starts only on explicit action', async () => {
    const user = userEvent.setup();
    const detail = {
      ...mockInstances[0],
      retuningSignal: {
        recommended: true,
        negativeCount: 3,
        positiveCount: 1,
        feedbackTotal: 4,
        threshold: 3,
        eligibleDocumentIds: ['travel-policy'],
        reasons: ['숙박비 한도 답변에 부정 피드백이 누적됐어요.'],
        action: 'START_RETUNE' as const,
        comparison: {
          beforeLabel: '현재 검색 설정',
          beforeQuality: 'FALLBACK' as const,
          afterLabel: '새 후보 비교',
          afterQuality: 'PENDING' as const,
        },
      },
    };
    vi.spyOn(ragApi, 'get').mockResolvedValue(detail);
    const retune = vi.spyOn(ragApi, 'retune').mockResolvedValue({ nextAction: 'TUNE_DOCUMENT' });
    renderWorkspace();

    const recommendation = await screen.findByRole('region', { name: '재튜닝 추천' });
    expect(recommendation).toHaveTextContent('숙박비 한도 답변에 부정 피드백이 누적됐어요.');
    expect(recommendation).toHaveTextContent(
      '관찰된 피드백: 부정 3건 · 권장 기준 3건 · 전체 4건 · 긍정 1건',
    );
    expect(recommendation).toHaveTextContent('전 · 현재 검색 설정');
    expect(recommendation).toHaveTextContent('후 · 새 후보 비교');
    expect(recommendation).toHaveTextContent(
      '개발용 fallback 결과라 실측 품질 비교에 사용하지 않아요.',
    );
    expect(recommendation).toHaveTextContent('실측 비교 결과를 기다리고 있어요.');

    await user.click(screen.getByRole('button', { name: '재튜닝 시작' }));
    await waitFor(() =>
      expect(retune).toHaveBeenCalledWith(
        'travel',
        ['travel-policy'],
        '숙박비 한도 답변에 부정 피드백이 누적됐어요.',
      ),
    );
  });

  it('does not present missing quality data as a retuning quality result', async () => {
    vi.spyOn(ragApi, 'get').mockResolvedValue({
      ...mockInstances[0],
      retuningSignal: {
        recommended: false,
        negativeCount: 1,
        threshold: 3,
        eligibleDocumentIds: ['travel-policy'],
        reasons: ['아직 권장 기준에 도달하지 않았어요.'],
        comparison: {
          beforeLabel: '현재 설정',
          beforeQuality: 'MISSING',
          afterLabel: '재튜닝 후 비교 결과',
          afterQuality: 'MISSING',
        },
      },
    });
    renderWorkspace();

    const recommendation = await screen.findByRole('region', { name: '재튜닝 추천' });
    expect(recommendation).toHaveTextContent('실측 품질 결과가 없어 비교 수치를 표시하지 않아요.');
    expect(screen.queryByRole('button', { name: '재튜닝 시작' })).not.toBeInTheDocument();
  });

  it('shows source provenance without storage URLs and starts reparse only when the original is available', async () => {
    const user = userEvent.setup();
    const detail = {
      ...mockInstances[0],
      documents: mockInstances[0].documents.map((document, index) => ({
        ...document,
        provenance:
          index === 0
            ? {
                checksum: 'a12bc34de56f78901234567890abcdef01234567890abcdef01234567890abcdef',
                deduplication: 'DUPLICATE_REUSED' as const,
                parser: 'PDF 구조 파서',
                parserVersion: 'v2.4',
                chunking: 'semantic',
                embeddingModel: 'BGE-M3',
                modelVersion: '2026.08',
                originalAvailable: true,
                reparse: {
                  available: true,
                  state: 'IDLE' as const,
                  impact: '원본을 다시 읽고 후보를 새로 준비합니다.',
                },
              }
            : {
                originalAvailable: false,
                reparse: { available: false, state: 'IDLE' as const },
              },
      })),
    };
    vi.spyOn(ragApi, 'get').mockResolvedValue(detail);
    const reparse = vi.spyOn(ragApi, 'reparseDocument').mockResolvedValue();
    const streamAnswer = vi
      .spyOn(ragApi, 'streamAnswer')
      .mockResolvedValue({ text: '검색 결과', citations: [], latencyMs: 1 });
    renderWorkspace();

    await user.click(await screen.findByRole('tab', { name: '문서' }));
    const provenance = await screen.findByRole('group', {
      name: '출장비_지급_규정.pdf 출처 및 처리 정보',
    });
    expect(provenance).toHaveTextContent('a12bc34de56f…cdef');
    expect(provenance).toHaveTextContent('같은 원본을 찾아 기존 처리 결과를 재사용함');
    expect(provenance).toHaveTextContent('PDF 구조 파서 · v2.4');
    expect(provenance).toHaveTextContent('semantic · BGE-M3 · 2026.08');
    expect(provenance).toHaveTextContent('원본을 다시 읽을 수 있음');
    expect(screen.queryByText(/s3:\/\/|storage\.internal/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '원본 다시 읽기' }));
    expect(await screen.findByRole('dialog', { name: '원본을 다시 읽을까요?' })).toHaveTextContent(
      '검색 범위에서 제외',
    );
    expect(screen.getByRole('button', { name: '취소' })).toHaveFocus();
    await user.click(screen.getByRole('button', { name: '다시 읽기 시작' }));
    await waitFor(() => expect(reparse).toHaveBeenCalledWith('travel', 'travel-policy'));
    expect(
      await screen.findAllByText(
        /출장비_지급_규정.pdf을\(를\) 다시 읽고 있어요 · 검색 범위에서 제외됨/,
      ),
    ).toHaveLength(2);
    const reparsedDocument = screen.getByRole('checkbox', { name: /출장비_지급_규정.pdf/ });
    expect(reparsedDocument).not.toBeChecked();
    expect(reparsedDocument).toBeDisabled();
    expect(screen.getByRole('checkbox', { name: /복리후생_안내.pdf/ })).toBeChecked();

    await user.type(screen.getByRole('textbox', { name: '검색 질문' }), '검색 범위를 확인해요');
    await user.click(screen.getByRole('button', { name: '질문하기' }));
    await waitFor(() =>
      expect(streamAnswer).toHaveBeenCalledWith(
        'travel',
        '검색 범위를 확인해요',
        ['benefits'],
        'balanced',
        expect.any(Object),
      ),
    );
    expect(screen.getByText('원본을 다시 읽을 수 없음')).toBeInTheDocument();
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

  it('explains an invalid-grounding fallback without exposing an internal status code', async () => {
    const user = userEvent.setup();
    vi.spyOn(ragApi, 'streamAnswer').mockResolvedValue({
      text: '문서 발췌 결과',
      citations: [],
      latencyMs: 10,
      generation: { fallback: true, fallbackReason: 'INVALID_GROUNDING' },
    });
    renderWorkspace();
    const question = await screen.findByRole('textbox', { name: '검색 질문' });
    await user.type(question, '근거를 확인해줘');
    await user.click(screen.getByRole('button', { name: '질문하기' }));

    expect(
      await screen.findByText('근거를 다시 확인하기 위해 문서 발췌 결과를 보여드려요.'),
    ).toBeInTheDocument();
    expect(screen.queryByText('INVALID_GROUNDING')).not.toBeInTheDocument();
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

  it('loads the selected citation source when moving within grouped evidence', async () => {
    const user = userEvent.setup();
    const evidence = vi.spyOn(ragApi, 'evidence').mockImplementation(async (url) => ({
      title:
        url === '/evidence/policy-2'
          ? '출장비_지급_규정.pdf · 제8조'
          : '출장비_지급_규정.pdf · 제5조',
      excerpt:
        url === '/evidence/policy-2' ? '두 번째 원문 위치입니다.' : '첫 번째 원문 위치입니다.',
      page: url === '/evidence/policy-2' ? 'p. 8' : 'p. 5',
    }));
    vi.spyOn(ragApi, 'streamAnswer').mockResolvedValue({
      text: '두 근거를 확인한 답변',
      citations: [
        {
          id: 'policy-1',
          title: '출장비_지급_규정.pdf',
          documentName: '출장비_지급_규정.pdf',
          excerpt: '첫 번째 인용',
          page: 'p. 5',
          navigateUrl: '/evidence/policy-1',
        },
        {
          id: 'policy-2',
          title: '출장비_지급_규정.pdf',
          documentName: '출장비_지급_규정.pdf',
          excerpt: '두 번째 인용',
          page: 'p. 8',
          navigateUrl: '/evidence/policy-2',
        },
        {
          id: 'benefits-1',
          title: '복리후생_안내.pdf',
          documentName: '복리후생_안내.pdf',
          excerpt: '다른 문서 인용',
          page: 'p. 2',
        },
      ],
      latencyMs: 10,
    });
    renderWorkspace();
    await user.type(await screen.findByRole('textbox', { name: '검색 질문' }), '근거를 비교해줘');
    await user.click(screen.getByRole('button', { name: '질문하기' }));
    await user.click(screen.getByRole('button', { name: '출장비_지급_규정.pdf 근거 2개 보기' }));
    await waitFor(() => expect(evidence).toHaveBeenCalledWith('/evidence/policy-1'));

    await user.click(screen.getByRole('button', { name: 'p. 8 · 두 번째 인용' }));
    await waitFor(() => expect(evidence).toHaveBeenCalledWith('/evidence/policy-2'));
    expect(await screen.findByText('두 번째 원문 위치입니다.')).toBeInTheDocument();
  });
});
