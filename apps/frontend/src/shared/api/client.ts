import type {
  ChatAnswer,
  ComparisonRound,
  CreateRagInput,
  EmbeddingModelRecommendation,
  PipelineCandidate,
  RagDocument,
  RagInstance,
  RagInstanceDetail,
  RagProcessingJob,
  RetrievalConfig,
} from './types';
import { candidateFixtures, mockInstances, mockRound } from '../mocks/ragFixtures';

const baseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '');
let localInstances = [...mockInstances];
type Json = Record<string, unknown>;

function base64FromBytes(bytes: Uint8Array): string {
  let binary = '';
  const chunkSize = 0x8000;
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }
  return btoa(binary);
}

export type AnswerStreamOptions = {
  signal?: AbortSignal;
  onUpdate?: (answer: Pick<ChatAnswer, 'text' | 'citations'>) => void;
};

function abortable<T>(operation: Promise<T>, signal?: AbortSignal): Promise<T> {
  if (!signal) return operation;
  return new Promise((resolve, reject) => {
    const abort = () => reject(new DOMException('답변 생성을 중단했어요.', 'AbortError'));
    if (signal.aborted) {
      abort();
      return;
    }
    signal.addEventListener('abort', abort, { once: true });
    operation.then(
      (value) => {
        signal.removeEventListener('abort', abort);
        resolve(value);
      },
      (error) => {
        signal.removeEventListener('abort', abort);
        reject(error);
      },
    );
  });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!baseUrl) throw new Error('Mock mode');
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(
      (payload as { detail?: { message?: string } }).detail?.message ??
        `요청에 실패했습니다 (${response.status}).`,
    );
  }
  return response.json() as Promise<T>;
}
const wait = (ms = 250) => new Promise((resolve) => window.setTimeout(resolve, ms));
const configMap: Record<string, RetrievalConfig> = {
  hybrid: 'HYBRID',
  hybrid_rerank: 'HYBRID_RERANK',
  dense: 'DENSE',
  bm25: 'BM25',
};
const chunkMap: Record<string, PipelineCandidate['chunkingStrategy']> = {
  document: 'FIXED',
  semantic: 'SEMANTIC',
  fixed: 'FIXED',
  hierarchical: 'HIERARCHICAL',
  table: 'HIERARCHICAL',
  ocr_hierarchical: 'HIERARCHICAL',
  ocr_semantic: 'SEMANTIC',
};

function locationLabel(location: unknown, fallback: unknown = ''): string {
  if (location && typeof location === 'object' && 'ordinal' in location) {
    const ordinal = (location as { ordinal?: unknown }).ordinal;
    return `${String(ordinal)}번째 문서 조각`;
  }
  if (typeof location === 'string' && location) return location;
  return fallback ? `${String(fallback)}번째 문서 조각` : '문서 원문';
}

function jobFromWire(job: Json | undefined): RagProcessingJob | undefined {
  if (!job) return undefined;
  const progress = (job.progress as Json | undefined) ?? {};
  return {
    id: String(job.id),
    state: String(job.state) as RagProcessingJob['state'],
    currentStep: String(job.current_step ?? '작업 상태를 확인하고 있어요.'),
    completed: Number(progress.completed ?? 0),
    total: Number(progress.total ?? 0),
    canRetry: Boolean(job.can_retry),
    canCancel: Boolean(job.can_cancel),
    errorMessage: typeof job.error_message === 'string' ? job.error_message : undefined,
    stages: ((job.stages as Json[] | undefined) ?? []).map((stage) => ({
      key: String(stage.key),
      label: String(stage.label),
      state: String(stage.state) as 'QUEUED' | 'SUCCEEDED' | 'FAILED',
    })),
  };
}

function pipelineFromWire(candidate: Json, result?: Json): PipelineCandidate {
  const citations = (result?.citations as Json[] | undefined) ?? [];
  const hasEvidence = citations.length > 0;
  return {
    id: String(candidate.id),
    chunkingStrategy: chunkMap[String(candidate.chunking_strategy)] ?? 'FIXED',
    retrievalConfig: configMap[String(candidate.retrieval_config)] ?? 'HYBRID',
    label: String(candidate.friendly_name ?? '검색 후보').replaceAll(' + ', ' · '),
    plainLabel: String(candidate.friendly_name ?? '검색 후보').split(' + ')[1] ?? '일반 검색',
    description: String(candidate.technical_description ?? ''),
    selectionCount: Number(candidate.selection_count ?? 0),
    chunkCount: Number(candidate.chunk_count ?? 0) || undefined,
    latencyMs: Number(result?.latency_ms ?? 0),
    answer: String(
      result?.answer ?? (hasEvidence ? '근거를 준비하고 있어요.' : '아직 비교 질문이 없어요.'),
    ),
    evidence: citations.map((citation) => ({
      id: String(citation.segment_id),
      title: String(citation.filename),
      excerpt: String(citation.excerpt),
      page: locationLabel(citation.location, citation.ordinal),
      navigateUrl: typeof citation.navigate_url === 'string' ? citation.navigate_url : undefined,
    })),
  };
}
function instanceFromWire(item: Json, detail = false): RagInstanceDetail {
  const rawDocs = (item.documents as Json[] | undefined) ?? [];
  const documents: RagDocument[] = rawDocs.map((document) => {
    const candidates = (document.candidates as Json[] | undefined) ?? [];
    const finalized = candidates.find(
      (candidate) => candidate.id === document.finalized_candidate_id,
    );
    return {
      id: String(document.id),
      name: String(document.filename),
      sourceType: String(document.content_type).includes('pdf') ? 'PDF' : 'TXT',
      status: 'PARSED',
      pipelineLabel: finalized ? pipelineFromWire(finalized).label : undefined,
      pipelineId: finalized ? String(finalized.id) : undefined,
    };
  });
  const candidates = rawDocs.flatMap((document) =>
    ((document.candidates as Json[] | undefined) ?? []).map((candidate) =>
      pipelineFromWire(candidate),
    ),
  );
  const latestJob = jobFromWire(item.latest_job as Json | undefined);
  const latestRound = item.latest_round as Json | undefined;
  const lastRound = latestRound
    ? {
        id: String(latestRound.id),
        question: String(latestRound.question),
        candidates: ((latestRound.results as Json[] | undefined) ?? []).map((result) =>
          pipelineFromWire(result.candidate as Json, result),
        ),
      }
    : undefined;
  return {
    id: String(item.id),
    name: String(item.name),
    status: String(item.status) as RagInstance['status'],
    embeddingModel: String(item.embedding_model),
    graphragEnabled: Boolean(item.graphrag_enabled),
    documents,
    candidates,
    createdAt: String(item.created_at),
    progress: latestJob
      ? {
          stage: 'READY',
          completed: latestJob.completed,
          total: latestJob.total,
          message: latestJob.currentStep,
        }
      : undefined,
    latestJob: detail ? latestJob : undefined,
    lastRound,
  };
}
function questionnaireFromInput(input: CreateRagInput) {
  return {
    primary_language: input.questionnaire.primaryLanguage,
    requires_on_premise: input.questionnaire.requiresOnPremise,
    budget: input.questionnaire.budget,
    multi_hop_questions: input.questionnaire.multiHopQuestions,
    embedding_model: input.embeddingModel,
  };
}

function recommendationFromWire(item: Json): EmbeddingModelRecommendation {
  return {
    id: String(item.id),
    label: String(item.label),
    reason: String(item.reason),
    tradeoff: String(item.tradeoff),
    recommended: Boolean(item.recommended),
  };
}

function fallbackRecommendations(
  input: CreateRagInput['questionnaire'],
): EmbeddingModelRecommendation[] {
  const items: EmbeddingModelRecommendation[] = [
    {
      id: 'BGE-M3',
      label: '균형형 다국어 검색',
      reason: '한국어·영어가 섞인 문서와 하이브리드 검색을 폭넓게 다룰 수 있어요.',
      tradeoff: '가벼운 모델보다 운영 자원이 더 필요할 수 있어요.',
      recommended: input.primaryLanguage === 'ko' && !input.requiresOnPremise,
    },
    {
      id: 'Qwen3-Embedding-0.6B',
      label: '자체 운영 우선',
      reason: '상대적으로 가벼워 사내·폐쇄망 환경에서 시작하기 좋습니다.',
      tradeoff: '복잡한 다국어 의미 검색은 실제 문서로 확인이 필요해요.',
      recommended: input.requiresOnPremise,
    },
    {
      id: 'EmbeddingGemma-300M',
      label: '경량 운영형',
      reason: '작은 운영 비용으로 빠르게 기준선을 만들고 싶을 때 적합합니다.',
      tradeoff: '난도가 높은 문서에서는 실측 벤치마크가 필요해요.',
      recommended: input.budget === 'low' && !input.requiresOnPremise,
    },
  ];
  return items.map((item, index) => ({
    ...item,
    recommended: item.recommended || (!items.some((choice) => choice.recommended) && index === 0),
  }));
}

export const ragApi = {
  async recommendEmbeddingModels(
    questionnaire: CreateRagInput['questionnaire'],
  ): Promise<EmbeddingModelRecommendation[]> {
    try {
      const data = await request<{ items: Json[] }>(
        '/api/v1/rag-instances/embedding-recommendations',
        {
          method: 'POST',
          body: JSON.stringify({
            primary_language: questionnaire.primaryLanguage,
            requires_on_premise: questionnaire.requiresOnPremise,
            budget: questionnaire.budget,
            multi_hop_questions: questionnaire.multiHopQuestions,
          }),
        },
      );
      return data.items.map(recommendationFromWire);
    } catch {
      await wait();
      return fallbackRecommendations(questionnaire);
    }
  },
  async list(): Promise<RagInstance[]> {
    try {
      const data = await request<{ items: Json[] }>('/api/v1/rag-instances');
      return data.items.map((item) => instanceFromWire(item));
    } catch {
      await wait();
      return localInstances;
    }
  },
  async get(id: string): Promise<RagInstanceDetail> {
    try {
      return instanceFromWire(await request<Json>(`/api/v1/rag-instances/${id}`), true);
    } catch {
      await wait();
      return localInstances.find((item) => item.id === id) ?? localInstances[0];
    }
  },
  async create(input: CreateRagInput): Promise<RagInstanceDetail> {
    try {
      return instanceFromWire(
        await request<Json>('/api/v1/rag-instances', {
          method: 'POST',
          body: JSON.stringify({ name: input.name, questionnaire: questionnaireFromInput(input) }),
        }),
      );
    } catch {
      const created: RagInstanceDetail = {
        id: `rag-${Date.now()}`,
        name: input.name,
        status: 'SETTING_UP',
        embeddingModel: input.embeddingModel,
        graphragEnabled: input.questionnaire.multiHopQuestions,
        documents: [],
        candidates: [],
        progress: { stage: 'WAITING_FOR_DOCUMENT', completed: 0, total: 0 },
        createdAt: new Date().toISOString(),
      };
      localInstances = [created, ...localInstances];
      return created;
    }
  },
  async upload(
    id: string,
    files: File[],
    reuseFinalizedPipeline = false,
  ): Promise<RagInstanceDetail> {
    try {
      const documents = await Promise.all(
        files.map(async (file) => {
          const bytes = new Uint8Array(await file.arrayBuffer());
          return {
            filename: file.name,
            content_type: file.type || 'application/octet-stream',
            content_base64: base64FromBytes(bytes),
          };
        }),
      );
      await request(`/api/v1/rag-instances/${id}/documents`, {
        method: 'POST',
        body: JSON.stringify({ documents, reuse_finalized_pipeline: reuseFinalizedPipeline }),
      });
      return this.get(id);
    } catch {
      await wait(450);
      const instance = localInstances.find((item) => item.id === id)!;
      instance.status = 'TUNING';
      instance.documents = files.map((file, index) => ({
        id: `${id}-${index}`,
        name: file.name,
        sourceType: (file.name.split('.').pop()?.toUpperCase() || 'TXT') as 'PDF',
        status: 'PARSED',
      }));
      instance.candidates = mockRound.candidates;
      instance.lastRound = mockRound;
      return instance;
    }
  },
  async cancelJob(jobId: string): Promise<void> {
    try {
      await request(`/api/v1/rag-jobs/${jobId}/cancel`, { method: 'POST' });
    } catch {
      await wait();
    }
  },
  async retryJob(jobId: string): Promise<void> {
    try {
      await request(`/api/v1/rag-jobs/${jobId}/retry`, { method: 'POST' });
    } catch {
      await wait();
    }
  },
  async compare(id: string, question: string, documentIds: string[]): Promise<ComparisonRound> {
    try {
      const data = await request<{ round: Json; results: Json[] }>(
        `/api/v1/rag-instances/${id}/tuning/compare`,
        { method: 'POST', body: JSON.stringify({ document_ids: documentIds, question }) },
      );
      return {
        id: String(data.round.id),
        question: String(data.round.question),
        candidates: data.results.map((result) =>
          pipelineFromWire(result.candidate as Json, result),
        ),
      };
    } catch {
      await wait(380);
      return {
        ...mockRound,
        id: `round-${Date.now()}`,
        question: question || mockRound.question,
        candidates: mockRound.candidates.map((candidate) => ({ ...candidate })),
      };
    }
  },
  async vote(roundId: string, candidateIds: string[]): Promise<void> {
    try {
      await request(`/api/v1/tuning-rounds/${roundId}/vote`, {
        method: 'POST',
        body: JSON.stringify({ candidate_ids: candidateIds }),
      });
    } catch {
      await wait();
    }
  },
  async finalize(id: string, documentId: string): Promise<void> {
    try {
      await request(`/api/v1/rag-instances/${id}/tuning/finalize`, {
        method: 'POST',
        body: JSON.stringify({ document_id: documentId }),
      });
    } catch {
      await wait();
    }
  },
  async answer(
    id: string,
    question: string,
    documentIds: string[],
    sensitivity = 'balanced',
  ): Promise<ChatAnswer> {
    try {
      const data = await request<Json>(`/api/v1/rag-instances/${id}/search`, {
        method: 'POST',
        body: JSON.stringify({ question, document_ids: documentIds, sensitivity }),
      });
      return {
        text: String(data.answer),
        citations: ((data.citations as Json[]) ?? []).map((citation) => ({
          id: String(citation.segment_id),
          title: String(citation.filename),
          excerpt: String(citation.excerpt),
          page: locationLabel(citation.location, citation.ordinal),
          navigateUrl:
            typeof citation.navigate_url === 'string' ? citation.navigate_url : undefined,
        })),
        latencyMs: 0,
      };
    } catch {
      await wait(400);
      return {
        text: question.includes('숙박')
          ? '국내 출장 숙박비는 1박 10만원을 한도로 합니다.'
          : '해외 출장 식비는 국가 등급에 따라 하루 80~150달러입니다.',
        citations: mockRound.candidates[1].evidence,
        latencyMs: 1240,
      };
    }
  },
  async streamAnswer(
    id: string,
    question: string,
    documentIds: string[],
    sensitivity = 'balanced',
    options: AnswerStreamOptions = {},
  ): Promise<ChatAnswer> {
    if (!baseUrl || typeof EventSource === 'undefined') {
      return abortable(this.answer(id, question, documentIds, sensitivity), options.signal);
    }
    const query = new URLSearchParams({ question, sensitivity });
    documentIds.forEach((documentId) => query.append('document_ids', documentId));
    return new Promise((resolve, reject) => {
      const source = new EventSource(
        `${baseUrl}/api/v1/rag-instances/${id}/search/stream?${query}`,
      );
      const startedAt = Date.now();
      let text = '';
      let citations: ChatAnswer['citations'] = [];
      let settled = false;
      const finish = (callback: () => void) => {
        if (settled) return;
        settled = true;
        source.close();
        options.signal?.removeEventListener('abort', abort);
        callback();
      };
      const abort = () =>
        finish(() => reject(new DOMException('답변 생성을 중단했어요.', 'AbortError')));
      const publish = () => options.onUpdate?.({ text, citations });
      source.addEventListener('citations', (event) => {
        try {
          citations = (JSON.parse((event as MessageEvent<string>).data) as Json[]).map(
            (citation) => ({
              id: String(citation.segment_id),
              title: String(citation.filename),
              excerpt: String(citation.excerpt),
              page: locationLabel(citation.location, citation.ordinal),
              navigateUrl:
                typeof citation.navigate_url === 'string' ? citation.navigate_url : undefined,
            }),
          );
          publish();
        } catch {
          // A malformed stream payload is handled by the terminal error state.
        }
      });
      source.addEventListener('token', (event) => {
        try {
          text += String((JSON.parse((event as MessageEvent<string>).data) as Json).token ?? '');
          publish();
        } catch {
          // Keep waiting for a valid terminal event instead of replacing existing content.
        }
      });
      source.addEventListener('done', () =>
        finish(() => resolve({ text, citations, latencyMs: Date.now() - startedAt })),
      );
      source.onerror = () =>
        finish(() =>
          reject(
            new Error('답변 연결이 끊겼어요. 지금까지 받은 내용을 확인하거나 다시 질문해 주세요.'),
          ),
        );
      if (options.signal?.aborted) abort();
      else options.signal?.addEventListener('abort', abort, { once: true });
    });
  },
  async feedback(id: string, rating: 1 | -1): Promise<void> {
    try {
      await request(`/api/v1/rag-instances/${id}/feedback`, {
        method: 'POST',
        body: JSON.stringify({ rating }),
      });
    } catch {
      await wait();
    }
  },
  async deleteDocument(id: string, documentId: string): Promise<void> {
    try {
      await request(`/api/v1/rag-instances/${id}/documents/${documentId}`, { method: 'DELETE' });
    } catch {
      await wait();
    }
  },
  async evidence(navigateUrl: string): Promise<{ title: string; excerpt: string; page: string }> {
    try {
      const data = await request<Json>(navigateUrl);
      const citation = data.citation as Json;
      const viewer = data.viewer as Json;
      return {
        title: String(citation.filename ?? viewer.filename),
        excerpt: String(viewer.content),
        page: locationLabel(citation.location, citation.ordinal),
      };
    } catch {
      await wait();
      throw new Error('원문 근거를 불러오지 못했어요.');
    }
  },
};
