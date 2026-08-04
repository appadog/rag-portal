import { afterEach, describe, expect, it, vi } from 'vitest';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('candidate exploration response mapping', () => {
  it('marks generated proposal variants instead of narrowed parent candidates', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.test');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          items: [
            {
              id: 'exploration-1',
              phase: 'PROPOSED',
              narrowed_candidate_ids: ['parent-candidate'],
              proposed: [
                {
                  candidate_id: 'generated-variant',
                  candidate: { id: 'generated-variant', friendly_name: '제안 변형' },
                },
              ],
              rationale: [{ parameter: 'top_k', reason: '근거 범위를 넓혀요.' }],
              rationales: ['top_k: 근거 범위를 넓혀요.'],
            },
          ],
        }),
      }),
    );
    const { ragApi } = await import('./client');

    const exploration = await ragApi.latestCandidateExploration('rag-1');

    expect(exploration?.proposedCandidateIds).toEqual(['generated-variant']);
    expect(exploration?.proposedCandidates).toEqual([
      { id: 'generated-variant', label: '제안 변형' },
    ]);
    expect(exploration?.rationales).toEqual(['top_k: 근거 범위를 넓혀요.']);
  });
});

describe('configured API safety and stream preflight', () => {
  it('renders a structured preflight conflict before opening EventSource', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.test');
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        eligible: false,
        conflicts: [
          {
            document_id: 'doc-pending',
            code: 'FULL_REINDEX_PENDING',
            message: '전체 문서 색인이 끝난 뒤 검색할 수 있어요.',
          },
        ],
      }),
    });
    const EventSource = vi.fn();
    vi.stubGlobal('fetch', fetch);
    vi.stubGlobal('EventSource', EventSource);
    const { ragApi, SearchPreflightError } = await import('./client');

    await expect(ragApi.streamAnswer('rag-1', '질문', ['doc-pending'])).rejects.toMatchObject({
      name: 'SearchPreflightError',
      code: 'FULL_REINDEX_PENDING',
      documentIds: ['doc-pending'],
    } satisfies Partial<InstanceType<typeof SearchPreflightError>>);
    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/api/v1/rag-instances/rag-1/search/preflight?document_ids=doc-pending',
      expect.any(Object),
    );
    expect(EventSource).not.toHaveBeenCalled();
  });

  it('maps REST grouped citations and grounded fallback metadata without inventing coverage', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.test');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          answer: '근거 기반 발췌 결과',
          citations: [
            {
              segment_id: 'segment-1',
              filename: '규정.pdf',
              excerpt: '숙박비 한도',
              location: 'p. 3',
            },
          ],
          grouped_citations: [
            {
              document_id: 'policy-document',
              document_name: '규정.pdf',
              citations: [{ segment_id: 'segment-1' }],
            },
          ],
          generation: { mode: 'EXTRACTIVE_FALLBACK', fallback_reason: 'INVALID_GROUNDING' },
        }),
      }),
    );
    const { ragApi } = await import('./client');

    const answer = await ragApi.answer('rag-1', '숙박비는?', ['policy-document']);

    expect(answer.citations[0]).toMatchObject({
      id: 'segment-1',
      documentId: 'policy-document',
      documentName: '규정.pdf',
    });
    expect(answer.documentCoverage).toEqual([
      { documentId: 'policy-document', documentName: '규정.pdf', citationCount: 1 },
    ]);
    expect(answer.generation).toMatchObject({
      fallback: true,
      fallbackReason: 'INVALID_GROUNDING',
    });
  });

  it('enriches SSE citations from terminal grouped metadata', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.test');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ eligible: true }) }),
    );
    class StreamDouble {
      private listeners = new Map<string, Array<(event: MessageEvent<string>) => void>>();

      constructor() {
        queueMicrotask(() => {
          this.emit('citations', [
            { segment_id: 'segment-2', filename: '복리후생.pdf', excerpt: '지원 기준', ordinal: 2 },
          ]);
          this.emit('token', { token: '지원 기준입니다.' });
          this.emit('done', {
            grouped_citations: [
              {
                document_id: 'benefits-document',
                document_name: '복리후생.pdf',
                citations: [{ segment_id: 'segment-2' }],
              },
            ],
            generation: { status: 'GROUNDED' },
          });
        });
      }

      addEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
        this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
      }

      close() {}

      private emit(type: string, data: unknown) {
        this.listeners
          .get(type)
          ?.forEach((listener) => listener({ data: JSON.stringify(data) } as MessageEvent<string>));
      }
    }
    vi.stubGlobal('EventSource', StreamDouble);
    const { ragApi } = await import('./client');

    const answer = await ragApi.streamAnswer('rag-1', '지원 기준은?', ['benefits-document']);

    expect(answer.text).toBe('지원 기준입니다.');
    expect(answer.citations[0]).toMatchObject({
      id: 'segment-2',
      documentId: 'benefits-document',
      documentName: '복리후생.pdf',
    });
    expect(answer.documentCoverage).toEqual([
      { documentId: 'benefits-document', documentName: '복리후생.pdf', citationCount: 1 },
    ]);
  });

  it('keeps an unsupported preflight endpoint compatible and never returns mocks for configured API failures', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.test');
    const fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: { message: 'Not found' } }),
    });
    vi.stubGlobal('fetch', fetch);
    const { ragApi } = await import('./client');

    await expect(ragApi.preflightSearch('rag-1', ['doc-1'])).resolves.toBeUndefined();
    await expect(ragApi.latestEmbeddingBenchmark()).resolves.toBeUndefined();
    fetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: { message: 'API를 사용할 수 없어요.' } }),
    });

    await expect(ragApi.list()).rejects.toThrow('API를 사용할 수 없어요.');
    await expect(
      ragApi.create({
        name: '새 지식 공간',
        embeddingModel: 'BGE-M3',
        questionnaire: {
          primaryLanguage: 'ko',
          requiresOnPremise: false,
          budget: 'medium',
          multiHopQuestions: false,
        },
      }),
    ).rejects.toThrow('API를 사용할 수 없어요.');
    await expect(ragApi.vote('round-1', ['candidate-1'])).rejects.toThrow(
      'API를 사용할 수 없어요.',
    );
    await expect(ragApi.latestCandidateExploration('rag-1')).rejects.toThrow(
      'API를 사용할 수 없어요.',
    );
  });
});
