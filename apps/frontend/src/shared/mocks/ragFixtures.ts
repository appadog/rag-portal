import type { ComparisonRound, PipelineCandidate, RagInstanceDetail } from '../api/types';

export const candidateFixtures: PipelineCandidate[] = [
  {
    id: 'article-hybrid',
    chunkingStrategy: 'ARTICLE',
    retrievalConfig: 'HYBRID',
    label: '조항 단위 · 일반 검색',
    plainLabel: '일반 검색',
    description: '문서의 조항과 제목을 함께 보존해, 규정·매뉴얼 질문을 안정적으로 찾습니다.',
    selectionCount: 2,
    latencyMs: 1180,
    answer: '해외 출장 식비는 국가 등급(A/B/C)에 따라 하루 80~150달러를 한도로 지급합니다.',
    evidence: [
      {
        id: 'ev-1',
        title: '출장비 지급 규정 · 제5조',
        excerpt: '해외 출장 시 국가 등급(A/B/C)에 따라 1일 80~150달러를 한도로 지급한다.',
        page: 'p. 3',
      },
    ],
  },
  {
    id: 'article-rerank',
    chunkingStrategy: 'ARTICLE',
    retrievalConfig: 'HYBRID_RERANK',
    label: '조항 단위 · 정밀 검색',
    plainLabel: '정밀 검색',
    description:
      '일반 검색 결과를 한 번 더 정리해, 비슷한 표현이 많은 문서에서 더 정확하게 답합니다.',
    selectionCount: 3,
    latencyMs: 1680,
    answer:
      '해외 출장 시 국가 등급(A/B/C)에 따라 하루 식비는 80~150달러입니다. 항공료는 이코노미 기준으로 정산합니다.',
    evidence: [
      {
        id: 'ev-2',
        title: '출장비 지급 규정 · 제5조',
        excerpt:
          '해외 출장 시 국가 등급(A/B/C)에 따라 1일 80~150달러를 한도로 지급하며, 항공료는 이코노미 클래스 기준 실비로 정산한다.',
        page: 'p. 3',
      },
    ],
  },
  {
    id: 'semantic-dense',
    chunkingStrategy: 'SEMANTIC',
    retrievalConfig: 'DENSE',
    label: '의미 단위 · 맥락 검색',
    plainLabel: '맥락 검색',
    description: '문장의 의미 흐름을 기준으로 나누어, 서술형 질문에 자연스러운 답을 찾습니다.',
    selectionCount: 0,
    latencyMs: 980,
    answer:
      '출장 식비는 출장지와 세부 규정에 따라 지급됩니다. 해외 출장의 정확한 한도는 관련 조항을 확인해 주세요.',
    evidence: [
      {
        id: 'ev-3',
        title: '출장비 지급 규정 · 제3~5조',
        excerpt: '국내 출장과 해외 출장의 지급 기준을 구분하여 안내합니다.',
        page: 'p. 2–3',
      },
    ],
  },
  {
    id: 'fixed-bm25',
    chunkingStrategy: 'FIXED',
    retrievalConfig: 'BM25',
    label: '기본 길이 · 키워드 검색',
    plainLabel: '키워드 검색',
    description: '문서의 정확한 단어와 숫자를 우선해 표, 코드, 식별자가 많은 자료에 유리합니다.',
    selectionCount: 0,
    latencyMs: 640,
    answer: '관련 문서를 충분히 찾지 못했습니다. 질문에 쓰인 표현을 바꿔 다시 시도해 주세요.',
    evidence: [],
  },
];

export const mockRound: ComparisonRound = {
  id: 'round-1',
  question: '해외 출장 갈 때 하루 식비 한도가 얼마야?',
  candidates: candidateFixtures,
};

export const mockInstances: RagInstanceDetail[] = [
  {
    id: 'travel',
    name: '출장비 규정 RAG',
    status: 'READY',
    embeddingModel: 'BGE-M3',
    graphragEnabled: false,
    documents: [
      {
        id: 'travel-policy',
        name: '출장비_지급_규정.pdf',
        sourceType: 'PDF',
        status: 'PARSED',
        pipelineLabel: '조항 단위 · 정밀 검색',
        pipelineId: 'article-rerank',
      },
      {
        id: 'benefits',
        name: '복리후생_안내.pdf',
        sourceType: 'PDF',
        status: 'PARSED',
        pipelineLabel: '문단 단위 · 일반 검색',
        pipelineId: 'article-hybrid',
      },
    ],
    candidates: candidateFixtures,
    lastRound: mockRound,
    createdAt: '2026-07-27T09:30:00Z',
  },
  {
    id: 'hr',
    name: '인사규정 RAG',
    status: 'PROCESSING',
    embeddingModel: 'Qwen3-Embedding-0.6B',
    graphragEnabled: true,
    documents: [
      { id: 'hr-policy', name: '인사규정_2026.pdf', sourceType: 'PDF', status: 'PARSING' },
    ],
    candidates: candidateFixtures,
    progress: {
      stage: 'INDEXING',
      completed: 2,
      total: 3,
      message: '세 번째 후보를 준비하고 있어요.',
    },
    createdAt: '2026-07-28T03:15:00Z',
  },
  {
    id: 'new',
    name: '새 지식 공간',
    status: 'SETTING_UP',
    embeddingModel: '선택 전',
    graphragEnabled: false,
    documents: [],
    candidates: candidateFixtures,
    progress: { stage: 'WAITING_FOR_DOCUMENT', completed: 0, total: 0 },
    createdAt: '2026-07-28T04:00:00Z',
  },
];
