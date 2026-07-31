export type RagStatus = 'SETTING_UP' | 'PROCESSING' | 'TUNING' | 'READY' | 'FAILED';
export type ProcessingStage =
  | 'WAITING_FOR_DOCUMENT'
  | 'PARSING'
  | 'CANDIDATES'
  | 'INDEXING'
  | 'READY';
export type RetrievalConfig = 'HYBRID' | 'HYBRID_RERANK' | 'DENSE' | 'BM25';
export type ChunkingStrategy = 'ARTICLE' | 'HIERARCHICAL' | 'SEMANTIC' | 'FIXED';

export interface RagDocument {
  id: string;
  name: string;
  sourceType: 'PDF' | 'DOCX' | 'CSV' | 'XLSX' | 'TXT';
  status: 'UPLOADED' | 'PARSING' | 'PARSED' | 'FAILED';
  pipelineLabel?: string;
  pipelineId?: string;
}

export interface RagInstance {
  id: string;
  name: string;
  status: RagStatus;
  embeddingModel: string;
  graphragEnabled: boolean;
  documents: RagDocument[];
  progress?: { stage: ProcessingStage; completed: number; total: number; message?: string };
  createdAt: string;
}

export interface RagProcessingJob {
  id: string;
  state:
    | 'QUEUED'
    | 'PARSING'
    | 'GENERATING_CANDIDATES'
    | 'INDEXING'
    | 'SUCCEEDED'
    | 'FAILED'
    | 'CANCELLED';
  currentStep: string;
  completed: number;
  total: number;
  canRetry: boolean;
  canCancel: boolean;
  errorMessage?: string;
  stages: { key: string; label: string; state: 'QUEUED' | 'SUCCEEDED' | 'FAILED' }[];
}

export interface PipelineCandidate {
  id: string;
  chunkingStrategy: ChunkingStrategy;
  retrievalConfig: RetrievalConfig;
  label: string;
  plainLabel: string;
  description: string;
  selectionCount: number;
  chunkCount?: number;
  latencyMs: number;
  answer: string;
  evidence: { id: string; title: string; excerpt: string; page: string; navigateUrl?: string }[];
  runtime?: {
    provider?: string;
    warning?: string;
    fallback: boolean;
  };
}

export interface ModelServiceStatus {
  key: string;
  technique: string;
  modelId: string;
  runtime: string;
  status: 'READY' | 'NOT_CONFIGURED' | 'UNAVAILABLE' | 'NOT_INSTALLED' | string;
  ready: boolean;
  detail: string;
}

export interface ExecutionPlan {
  embeddingModel: string;
  ready: boolean;
  fallbackPolicy: string;
  requiredServices: ModelServiceStatus[];
}

export interface SearchContextSnapshot {
  documentIds: string[];
  documentNames: string[];
  sensitivity: string;
}

export interface ComparisonRound {
  id: string;
  question: string;
  candidates: PipelineCandidate[];
}

export interface RagInstanceDetail extends RagInstance {
  candidates: PipelineCandidate[];
  lastRound?: ComparisonRound;
  latestJob?: RagProcessingJob;
}

export interface CreateRagInput {
  name: string;
  embeddingModel: string;
  questionnaire: {
    primaryLanguage: string;
    requiresOnPremise: boolean;
    budget: string;
    multiHopQuestions: boolean;
  };
}

export interface EmbeddingModelRecommendation {
  id: string;
  label: string;
  reason: string;
  tradeoff: string;
  recommended: boolean;
}

export interface ChatAnswer {
  text: string;
  citations: { id: string; title: string; excerpt: string; page: string; navigateUrl?: string }[];
  latencyMs: number;
  context?: SearchContextSnapshot;
  artifactId?: string;
  runtime?: {
    provider?: string;
    warning?: string;
    fallback: boolean;
  };
}
