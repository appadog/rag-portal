export type RagStatus = 'SETTING_UP' | 'PROCESSING' | 'TUNING' | 'READY' | 'FAILED';
export type ProcessingStage =
  | 'WAITING_FOR_DOCUMENT'
  | 'PARSING'
  | 'CANDIDATES'
  | 'INDEXING'
  | 'READY';
export type RetrievalConfig = 'HYBRID' | 'HYBRID_RERANK' | 'DENSE' | 'BM25';
export type ChunkingStrategy = 'ARTICLE' | 'HIERARCHICAL' | 'SEMANTIC' | 'FIXED';

export interface Citation {
  id: string;
  title: string;
  excerpt: string;
  page: string;
  navigateUrl?: string;
  documentId?: string;
  documentName?: string;
}

export interface SearchDocumentCoverage {
  documentId?: string;
  documentName: string;
  citationCount: number;
}

export interface RagDocument {
  id: string;
  name: string;
  sourceType: 'PDF' | 'DOCX' | 'CSV' | 'XLSX' | 'TXT';
  status: 'UPLOADED' | 'PARSING' | 'PARSED' | 'FAILED';
  pipelineLabel?: string;
  pipelineId?: string;
  comparisonScope?: 'FULL' | 'SAMPLE';
  estimatedChunkCount?: number;
  comparisonChunkCount?: number;
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
  evidence: Citation[];
  preparation?: {
    state: 'PREPARING' | 'READY' | 'FAILED';
    ready: boolean;
    error?: string;
    preparedAt?: string;
  };
  comparisonState?: 'READY' | 'NO_EVIDENCE' | 'PREPARING' | 'FAILED';
  comparisonStateDetail?: string;
  generation?: GroundedGenerationMetadata;
  runtime?: {
    provider?: string;
    warning?: string;
    fallback: boolean;
  };
}

export interface GroundedGenerationMetadata {
  status?: string;
  fallback: boolean;
  provider?: string;
  detail?: string;
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
  fullReindexJob?: RagProcessingJob;
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

export interface EmbeddingBenchmarkRun {
  id: string;
  corpusLabel: string;
  queryCount: number;
  createdAt: string;
}

export interface EmbeddingBenchmarkResult {
  modelId: string;
  recallAt1: number | null;
  recallAt5: number | null;
  mrr: number | null;
  averageLatencyMs: number | null;
  dimension: number | null;
  provider: string;
  status: string;
}

export interface EmbeddingBenchmark {
  run: EmbeddingBenchmarkRun;
  results: EmbeddingBenchmarkResult[];
}

export interface ChatAnswer {
  text: string;
  citations: Citation[];
  latencyMs: number;
  context?: SearchContextSnapshot;
  artifactId?: string;
  runtime?: {
    provider?: string;
    warning?: string;
    fallback: boolean;
  };
  generation?: GroundedGenerationMetadata;
  documentCoverage?: SearchDocumentCoverage[];
}
