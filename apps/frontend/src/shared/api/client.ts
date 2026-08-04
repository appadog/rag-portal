import type {
  ChatAnswer,
  CandidateExploration,
  Citation,
  ComparisonRound,
  CreateRagInput,
  DocumentProvenance,
  EmbeddingBenchmark,
  EmbeddingBenchmarkResult,
  EmbeddingModelRecommendation,
  ExecutionPlan,
  GroundedGenerationMetadata,
  ModelServiceStatus,
  PipelineCandidate,
  RagDocument,
  RagInstance,
  RagInstanceDetail,
  RagProcessingJob,
  RetuneStart,
  RetrievalConfig,
  RetuningComparisonState,
  RetuningQualityState,
  RetuningSignal,
  SearchDocumentCoverage,
} from './types';
import { candidateFixtures, mockInstances, mockRound } from '../mocks/ragFixtures';

const baseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '');
let localInstances = [...mockInstances];
type Json = Record<string, unknown>;

class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly payload: Json,
  ) {
    super(message);
    this.name = 'ApiRequestError';
  }
}

export class SearchPreflightError extends Error {
  constructor(
    message: string,
    readonly documentIds: string[],
    readonly code?: string,
  ) {
    super(message);
    this.name = 'SearchPreflightError';
  }
}

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
  onUpdate?: (answer: Pick<ChatAnswer, 'text' | 'citations' | 'generation'>) => void;
};

function abortable<T>(operation: Promise<T>, signal?: AbortSignal): Promise<T> {
  if (!signal) return operation;
  return new Promise((resolve, reject) => {
    const abort = () =>
      reject(
        new DOMException(
          '이 화면의 답변 표시를 중단했어요. 서버 작업은 계속될 수 있어요.',
          'AbortError',
        ),
      );
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
    const payload = (await response.json().catch(() => ({}))) as Json;
    const detail = payload.detail as Json | undefined;
    throw new ApiRequestError(
      (typeof detail?.message === 'string' ? detail.message : undefined) ??
        `요청에 실패했습니다 (${response.status}).`,
      response.status,
      payload,
    );
  }
  return response.json() as Promise<T>;
}
const wait = (ms = 250) => new Promise((resolve) => window.setTimeout(resolve, ms));

function fallbackOnlyWithoutApi(error: unknown): void {
  if (baseUrl) throw error;
}

function preflightConflictFromPayload(
  payload: Json,
  fallbackDocumentIds: string[],
  fallbackMessage?: string,
): SearchPreflightError {
  const detail = payload.detail as Json | undefined;
  const response = detail ?? payload;
  const conflicts = Array.isArray(response.conflicts)
    ? response.conflicts.filter((item): item is Json => Boolean(item) && typeof item === 'object')
    : [response];
  const documentIds = Array.from(
    new Set(
      conflicts.flatMap((conflict) => {
        const id = conflict.document_id ?? conflict.id;
        return typeof id === 'string' ? [id] : [];
      }),
    ),
  );
  const first = conflicts[0] ?? {};
  const code = typeof first.code === 'string' ? first.code : undefined;
  const message =
    typeof first.message === 'string'
      ? first.message
      : code === 'FULL_REINDEX_PENDING'
        ? '전체 문서 색인이 끝날 때까지 기다린 뒤 다시 검색해 주세요.'
        : code === 'FULL_REINDEX_FAILED'
          ? '전체 문서 색인을 다시 시도한 뒤 검색해 주세요.'
          : code === 'DOCUMENT_NOT_FINALIZED'
            ? '문서 비교와 확정을 마친 뒤 검색해 주세요.'
            : (fallbackMessage ?? '검색을 시작하기 전에 문서 준비 상태를 확인하지 못했어요.');
  return new SearchPreflightError(
    message,
    documentIds.length ? documentIds : fallbackDocumentIds,
    code,
  );
}

function preflightConflict(error: unknown, fallbackDocumentIds: string[]): SearchPreflightError {
  if (error instanceof ApiRequestError)
    return preflightConflictFromPayload(error.payload, fallbackDocumentIds, error.message);
  return new SearchPreflightError(
    (error as Error).message || '검색을 시작하기 전에 문서 준비 상태를 확인하지 못했어요.',
    fallbackDocumentIds,
  );
}
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

function citationFromWire(citation: Json): Citation {
  const documentName =
    typeof citation.document_name === 'string'
      ? citation.document_name
      : typeof citation.filename === 'string'
        ? citation.filename
        : undefined;
  return {
    id: String(citation.segment_id ?? citation.id ?? ''),
    title: String(citation.filename ?? documentName ?? '문서 근거'),
    excerpt: String(citation.excerpt),
    page: locationLabel(citation.location, citation.ordinal),
    navigateUrl: typeof citation.navigate_url === 'string' ? citation.navigate_url : undefined,
    documentId: typeof citation.document_id === 'string' ? citation.document_id : undefined,
    documentName,
  };
}

function groupedCitationDocuments(data: Json) {
  return ((data.grouped_citations as Json[] | undefined) ?? []).map((group) => ({
    documentId: typeof group.document_id === 'string' ? group.document_id : undefined,
    documentName: String(group.document_name ?? group.filename ?? '문서 근거'),
    citationIds: new Set(
      ((group.citations as Json[] | undefined) ?? []).map((citation) =>
        String(citation.segment_id ?? citation.id ?? ''),
      ),
    ),
  }));
}

function enrichCitationDocuments(citations: Citation[], data: Json): Citation[] {
  const groups = groupedCitationDocuments(data);
  return citations.map((mapped) => {
    const group = groups.find((item) => item.citationIds.has(mapped.id));
    return {
      ...mapped,
      documentId: mapped.documentId ?? group?.documentId,
      documentName: mapped.documentName ?? group?.documentName,
      title: mapped.title === '문서 근거' ? (group?.documentName ?? mapped.title) : mapped.title,
    };
  });
}

function citationsFromWire(data: Json): Citation[] {
  return enrichCitationDocuments(
    ((data.citations as Json[] | undefined) ?? []).map(citationFromWire),
    data,
  );
}

function coverageFromWire(data: Json): SearchDocumentCoverage[] | undefined {
  const coverage = data.document_coverage as Json[] | undefined;
  if (coverage?.length)
    return coverage.map((item) => ({
      documentId: typeof item.document_id === 'string' ? item.document_id : undefined,
      documentName: String(item.document_name ?? item.filename ?? '문서 근거'),
      citationCount: Number(item.citation_count ?? item.citations ?? 0),
    }));
  const groups = groupedCitationDocuments(data);
  return groups.length
    ? groups.map((group) => ({
        documentId: group.documentId,
        documentName: group.documentName,
        citationCount: group.citationIds.size,
      }))
    : undefined;
}

function jobFromWire(job: Json | undefined): RagProcessingJob | undefined {
  if (!job) return undefined;
  const progress = (job.progress as Json | undefined) ?? {};
  const recovery = (job.recovery as Json | undefined) ?? {};
  const deadLetter = (job.dead_letter as Json | undefined) ?? {};
  const lifecycle = (job.lifecycle as Json | undefined) ?? {};
  return {
    id: String(job.id),
    state: String(job.state) as RagProcessingJob['state'],
    currentStep: String(job.current_step ?? '작업 상태를 확인하고 있어요.'),
    completed: Number(progress.completed ?? 0),
    total: Number(progress.total ?? 0),
    canRetry: Boolean(job.can_retry ?? job.can_recover ?? recovery.can_retry),
    canCancel: Boolean(job.can_cancel),
    errorMessage: typeof job.error_message === 'string' ? job.error_message : undefined,
    stages: ((job.stages as Json[] | undefined) ?? []).map((stage) => ({
      key: String(stage.key),
      label: String(stage.label),
      state: String(stage.state) as 'QUEUED' | 'SUCCEEDED' | 'FAILED',
    })),
    kind: typeof job.kind === 'string' ? job.kind : undefined,
    attempt: typeof job.attempt === 'number' ? job.attempt : undefined,
    createdAt: typeof job.created_at === 'string' ? job.created_at : undefined,
    completedAt: typeof job.completed_at === 'string' ? job.completed_at : undefined,
    operationalState:
      typeof recovery.state === 'string'
        ? recovery.state
        : typeof deadLetter.state === 'string'
          ? deadLetter.state
          : deadLetter.active === true
            ? 'DEAD_LETTER'
            : typeof lifecycle.state === 'string'
              ? lifecycle.state
              : typeof job.operational_state === 'string'
                ? job.operational_state
                : undefined,
  };
}

function serviceFromWire(service: Json): ModelServiceStatus {
  return {
    key: String(service.key),
    technique: String(service.technique),
    modelId: String(service.model_id),
    runtime: String(service.runtime),
    status: String(service.status),
    ready: Boolean(service.ready),
    detail: String(service.detail ?? '모델 서비스 상태를 확인할 수 없어요.'),
  };
}

function planFromWire(plan: Json): ExecutionPlan {
  return {
    embeddingModel: String(plan.embedding_model),
    ready: Boolean(plan.ready),
    fallbackPolicy: String(plan.fallback_policy ?? ''),
    requiredServices: ((plan.required_services as Json[] | undefined) ?? []).map(serviceFromWire),
  };
}

function runtimeFromWire(metadata: Json | undefined, candidate: Json | undefined) {
  const index = (candidate?.index as Json | undefined) ?? {};
  const provider =
    typeof metadata?.provider === 'string'
      ? metadata.provider
      : typeof index.embedding_provider === 'string'
        ? index.embedding_provider
        : undefined;
  const warning =
    typeof metadata?.warning === 'string'
      ? metadata.warning
      : typeof index.warning === 'string'
        ? index.warning
        : undefined;
  return {
    provider,
    warning,
    fallback:
      Boolean(warning) || provider === 'legacy-lexical' || provider === 'development-fallback',
  };
}

function generationFromWire(metadata: Json | undefined): GroundedGenerationMetadata | undefined {
  const generation =
    (metadata?.generation_metadata as Json | undefined) ??
    (metadata?.generation as Json | undefined) ??
    metadata;
  const status =
    typeof generation?.status === 'string'
      ? generation.status
      : typeof generation?.state === 'string'
        ? generation.state
        : typeof metadata?.generation_status === 'string'
          ? metadata.generation_status
          : undefined;
  const provider = typeof generation?.provider === 'string' ? generation.provider : undefined;
  const detail =
    typeof generation?.detail === 'string'
      ? generation.detail
      : typeof generation?.message === 'string'
        ? generation.message
        : undefined;
  const fallback =
    typeof generation?.fallback === 'boolean'
      ? generation.fallback
      : typeof generation?.mode === 'string'
        ? generation.mode.toLowerCase().includes('fallback') ||
          generation.mode.toLowerCase().includes('extractive')
        : false;
  const fallbackReason =
    typeof generation?.fallback_reason === 'string' ? generation.fallback_reason : undefined;
  const groundingValid =
    typeof generation?.grounding_valid === 'boolean' ? generation.grounding_valid : undefined;
  return status || provider || detail || fallback || fallbackReason || groundingValid !== undefined
    ? { status, fallback, provider, detail, fallbackReason, groundingValid }
    : undefined;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string' && Boolean(item.trim()))
    : [];
}

function retuningReasonCopy(reason: string): string {
  const labels: Record<string, string> = {
    RECENT_NEGATIVE_FEEDBACK_THRESHOLD: '최근 부정 피드백의 가중치가 권장 기준에 도달했어요.',
    ANSWER_INTEGRITY_EVENTS_THRESHOLD:
      '저장된 답변 근거·fallback 점검 신호가 권장 기준에 도달했어요.',
    FEEDBACK_AND_ANSWER_INTEGRITY: '부정 피드백과 답변 점검 신호가 함께 관찰됐어요.',
    BENCHMARK_NOT_QUALITY_EVIDENCE:
      'fallback·미완료 벤치마크는 품질 점수 근거로 사용하지 않았어요.',
  };
  return labels[reason] ?? reason;
}

function retuningQualityFromWire(value: Json | undefined): RetuningQualityState {
  if (!value) return 'MISSING';
  const status = String(value.status ?? value.quality_status ?? '').toLowerCase();
  if (value.fallback === true || status.includes('fallback')) return 'FALLBACK';
  if (status.includes('pending') || status.includes('running') || status.includes('queued'))
    return 'PENDING';
  if (
    status.includes('measured') ||
    status.includes('observed') ||
    status.includes('verified') ||
    value.measured === true
  )
    return 'MEASURED';
  return 'MISSING';
}

function retuningSignalFromWire(item: Json): RetuningSignal | undefined {
  const retuning = item.retuning as Json | undefined;
  const preview = item.retune_preview as Json | undefined;
  const signal =
    (item.retuning_signal as Json | undefined) ??
    (retuning?.signal as Json | undefined) ??
    (preview?.signal as Json | undefined);
  if (!signal && !retuning && !preview) return undefined;
  const inputs =
    (signal?.inputs as Json | undefined) ??
    (retuning?.recommendation_inputs as Json | undefined) ??
    (preview?.recommendation_inputs as Json | undefined) ??
    {};
  const feedbackInput = (inputs.feedback as Json | undefined) ?? {};
  const benchmarkInput = (inputs.benchmark_provider as Json | undefined) ?? {};
  const comparison =
    (retuning?.before_after as Json | undefined) ??
    (preview?.before_after as Json | undefined) ??
    (retuning?.comparison as Json | undefined) ??
    (preview?.comparison as Json | undefined) ??
    {};
  const before =
    (comparison.before as Json | undefined) ??
    (comparison.baseline as Json | undefined) ??
    (retuning?.baseline_snapshot as Json | undefined) ??
    (preview?.baseline_snapshot as Json | undefined);
  const after =
    (comparison.after as Json | undefined) ??
    (comparison.outcome as Json | undefined) ??
    (retuning?.after_outcome as Json | undefined) ??
    (preview?.after_outcome as Json | undefined);
  const reasons = [
    ...stringList(signal?.reasons),
    ...stringList(signal?.recommendation_reasons),
    ...stringList(inputs.reasons),
    ...stringList(retuning?.reasons),
  ].map(retuningReasonCopy);
  const message =
    typeof signal?.message === 'string'
      ? signal.message
      : typeof retuning?.message === 'string'
        ? retuning.message
        : undefined;
  if (!reasons.length && message) reasons.push(message);
  const comparisonState: RetuningComparisonState = {
    beforeLabel:
      typeof before?.label === 'string'
        ? before.label
        : typeof before?.name === 'string'
          ? before.name
          : '현재 설정',
    beforeQuality: before
      ? retuningQualityFromWire(before)
      : benchmarkInput.status === 'REAL_PROVIDER_EVIDENCE'
        ? 'MEASURED'
        : benchmarkInput.status === 'NOT_RUN'
          ? 'MISSING'
          : 'FALLBACK',
    afterLabel:
      typeof after?.label === 'string'
        ? after.label
        : typeof after?.name === 'string'
          ? after.name
          : '재튜닝 후 비교 결과',
    afterQuality: after ? retuningQualityFromWire(after) : 'PENDING',
    outcomeArtifactId:
      typeof after?.artifact_id === 'string'
        ? after.artifact_id
        : typeof comparison.outcome_artifact_id === 'string'
          ? comparison.outcome_artifact_id
          : undefined,
  };
  return {
    recommended: Boolean(signal?.recommended ?? retuning?.recommended ?? preview?.recommended),
    negativeCount: Number(signal?.negative_count ?? inputs.negative_count ?? 0),
    positiveCount:
      typeof (signal?.positive_count ?? feedbackInput.positive_count ?? inputs.positive_count) ===
      'number'
        ? Number(signal?.positive_count ?? feedbackInput.positive_count ?? inputs.positive_count)
        : undefined,
    feedbackTotal:
      typeof (signal?.total ?? signal?.feedback_total ?? feedbackInput.total ?? inputs.total) ===
      'number'
        ? Number(signal?.total ?? signal?.feedback_total ?? feedbackInput.total ?? inputs.total)
        : undefined,
    threshold: Number(signal?.threshold ?? inputs.threshold ?? 0),
    thresholdKind: signal?.threshold_details ? 'WEIGHTED_NEGATIVE_FEEDBACK' : 'COUNT',
    eligibleDocumentIds: stringList(signal?.eligible_document_ids ?? inputs.eligible_document_ids),
    reasons,
    action:
      signal?.action === 'START_RETUNE' || retuning?.action === 'START_RETUNE'
        ? 'START_RETUNE'
        : undefined,
    policyVersion:
      typeof signal?.version === 'string'
        ? signal.version
        : typeof inputs.policy_version === 'string'
          ? inputs.policy_version
          : typeof retuning?.policy_version === 'string'
            ? retuning.policy_version
            : undefined,
    comparison: comparisonState,
  };
}

function explorationEvidenceFromWire(raw: Json): CandidateExploration['evidenceBoundary'] {
  const evidence = (raw.evidence as Json | undefined) ?? {};
  const benchmark =
    (evidence.benchmark as Json | undefined) ?? (raw.benchmark as Json | undefined) ?? {};
  const status = String(
    benchmark.status ?? evidence.status ?? raw.evidence_status ?? raw.benchmark_status ?? '',
  ).toLowerCase();
  if (benchmark.fallback === true || evidence.fallback === true || status.includes('fallback'))
    return 'FALLBACK';
  if (status.includes('pending') || status.includes('running')) return 'PENDING';
  if (status.includes('measured') || status.includes('observed') || status.includes('verified'))
    return 'MEASURED';
  return 'MISSING';
}

function explorationRationales(value: unknown): string[] {
  if (Array.isArray(value))
    return value.flatMap((item) => {
      if (typeof item === 'string' && item.trim()) return [item];
      if (item && typeof item === 'object') {
        const raw = item as Json;
        const parameter = typeof raw.parameter === 'string' ? raw.parameter : undefined;
        const reason =
          typeof raw.reason === 'string'
            ? raw.reason
            : typeof raw.rationale === 'string'
              ? raw.rationale
              : typeof raw.label === 'string'
                ? raw.label
                : undefined;
        return reason ? [parameter ? `${parameter}: ${reason}` : reason] : [];
      }
      return [];
    });
  return [];
}

function candidateExplorationFromWire(item: Json): CandidateExploration | undefined {
  const raw =
    (item.candidate_exploration as Json | undefined) ?? (item.exploration as Json | undefined);
  if (!raw) return undefined;
  const pool = (raw.pool as Json | undefined) ?? (raw.candidate_pool as Json | undefined) ?? {};
  const proposedRaw = raw.proposed ?? raw.narrowed_candidates ?? raw.proposal;
  const proposed = !Array.isArray(proposedRaw) ? ((proposedRaw as Json | undefined) ?? {}) : {};
  const proposalItems = Array.isArray(proposedRaw)
    ? proposedRaw.filter(
        (proposal): proposal is Json => Boolean(proposal) && typeof proposal === 'object',
      )
    : [];
  const rollback = (raw.rollback as Json | undefined) ?? (raw.restore as Json | undefined) ?? {};
  const proposedCandidateIds = stringList(
    proposed.candidate_ids ??
      proposed.ids ??
      raw.proposed_candidate_ids ??
      raw.narrowed_candidate_ids,
  );
  const proposalCandidateIds = proposalItems
    .map((proposal) => {
      const candidate = proposal.candidate as Json | undefined;
      return typeof proposal.candidate_id === 'string'
        ? proposal.candidate_id
        : typeof candidate?.id === 'string'
          ? candidate.id
          : undefined;
    })
    .filter((candidateId): candidateId is string => Boolean(candidateId));
  const proposedCandidates = proposalItems
    .map((proposal) => {
      const candidate = proposal.candidate as Json | undefined;
      const id =
        typeof proposal.candidate_id === 'string'
          ? proposal.candidate_id
          : typeof candidate?.id === 'string'
            ? candidate.id
            : undefined;
      const label =
        typeof candidate?.friendly_name === 'string'
          ? candidate.friendly_name
          : typeof proposal.base_friendly_name === 'string'
            ? proposal.base_friendly_name
            : undefined;
      return id && label ? { id, label } : undefined;
    })
    .filter((candidate): candidate is { id: string; label: string } => Boolean(candidate));
  const rationales = Array.from(
    new Set([
      ...explorationRationales(raw.rationales),
      ...explorationRationales(raw.rationale),
      ...explorationRationales(raw.reasons),
      ...explorationRationales(raw.parameter_changes),
      ...explorationRationales(proposed.rationales),
      ...proposalItems.flatMap((proposal) => {
        const rationale = proposal.rationale as Json | undefined;
        const retrieval = rationale?.retrieval_change as Json | undefined;
        return explorationRationales([
          rationale?.parameter_change_reason,
          retrieval
            ? `검색 방식: ${String(retrieval.from ?? '')} → ${String(retrieval.to ?? '')}`
            : undefined,
        ]);
      }),
    ]),
  ).slice(0, 5);
  return {
    id: String(raw.id ?? ''),
    phase: String(raw.phase ?? raw.state ?? 'EXPLORING'),
    poolCount: Array.isArray(raw.pool)
      ? raw.pool.length
      : typeof pool.count === 'number'
        ? pool.count
        : typeof raw.pool_count === 'number'
          ? raw.pool_count
          : typeof raw.candidate_pool_count === 'number'
            ? raw.candidate_pool_count
            : undefined,
    proposedCandidateIds: proposalCandidateIds.length ? proposalCandidateIds : proposedCandidateIds,
    proposedCandidates,
    rationales,
    evidenceBoundary: explorationEvidenceFromWire(raw),
    rollback:
      rollback.supported === true || rollback.available === true || rollback.enabled === true
        ? {
            canRollback: rollback.status !== 'ROLLED_BACK' && rollback.rollback_supported !== false,
            canRestore: rollback.restore_supported === true,
            state: typeof rollback.state === 'string' ? rollback.state : undefined,
          }
        : undefined,
  };
}

function provenanceFromWire(document: Json, candidate: Json | undefined, embeddingModel: unknown) {
  const provenance =
    (document.provenance as Json | undefined) ??
    (document.source_provenance as Json | undefined) ??
    {};
  const source =
    (provenance.source as Json | undefined) ?? (document.source as Json | undefined) ?? {};
  const processing =
    (provenance.processing as Json | undefined) ?? (document.processing as Json | undefined) ?? {};
  const parserMetadata = (provenance.parser as Json | undefined) ?? {};
  const chunkingMetadata = (provenance.chunking as Json | undefined) ?? {};
  const modelMetadata = (provenance.model as Json | undefined) ?? {};
  const dedup =
    (provenance.deduplication as Json | undefined) ??
    (provenance.dedup as Json | undefined) ??
    (source.deduplication as Json | undefined) ??
    (document.deduplication as Json | undefined) ??
    (document.dedup as Json | undefined) ??
    {};
  const reparse =
    (provenance.reparse as Json | undefined) ?? (document.reparse as Json | undefined) ?? {};
  const checksum =
    typeof provenance.checksum === 'string'
      ? provenance.checksum
      : typeof source.checksum === 'string'
        ? source.checksum
        : typeof source.checksum_sha256 === 'string'
          ? source.checksum_sha256
          : typeof document.checksum === 'string'
            ? document.checksum
            : undefined;
  const rawDedup = String(dedup.outcome ?? dedup.status ?? document.dedup_outcome ?? '');
  const deduplication: DocumentProvenance['deduplication'] = rawDedup
    ? rawDedup.includes('REUSED') || rawDedup.includes('DUPLICATE')
      ? rawDedup.includes('REPLACED')
        ? 'DUPLICATE_REPLACED'
        : 'DUPLICATE_REUSED'
      : rawDedup.includes('NEW') || rawDedup.includes('STORED') || rawDedup.includes('CREATED')
        ? 'NEW_SOURCE'
        : 'UNKNOWN'
    : undefined;
  const originalAvailable =
    typeof provenance.original_available === 'boolean'
      ? provenance.original_available
      : typeof source.original_available === 'boolean'
        ? source.original_available
        : typeof source.storage_key === 'string'
          ? true
          : typeof document.original_available === 'boolean'
            ? document.original_available
            : undefined;
  const reparseAvailable =
    typeof reparse.available === 'boolean'
      ? reparse.available
      : typeof reparse.allowed === 'boolean'
        ? reparse.allowed
        : originalAvailable === true
          ? true
          : undefined;
  const parser =
    typeof processing.parser === 'string'
      ? processing.parser
      : typeof parserMetadata.parser === 'string'
        ? parserMetadata.parser
        : typeof provenance.parser === 'string'
          ? provenance.parser
          : typeof document.parser === 'string'
            ? document.parser
            : undefined;
  const parserVersion =
    typeof processing.parser_version === 'string'
      ? processing.parser_version
      : typeof parserMetadata.version === 'string'
        ? parserMetadata.version
        : typeof provenance.parser_version === 'string'
          ? provenance.parser_version
          : typeof document.parser_version === 'string'
            ? document.parser_version
            : undefined;
  const chunking =
    typeof processing.chunking === 'string'
      ? processing.chunking
      : typeof processing.chunking_strategy === 'string'
        ? processing.chunking_strategy
        : typeof chunkingMetadata.strategy === 'string'
          ? chunkingMetadata.strategy
          : typeof candidate?.chunking_strategy === 'string'
            ? candidate.chunking_strategy
            : undefined;
  const modelVersion =
    typeof processing.model_version === 'string'
      ? processing.model_version
      : typeof modelMetadata.version === 'string'
        ? modelMetadata.version
        : typeof provenance.model_version === 'string'
          ? provenance.model_version
          : typeof document.model_version === 'string'
            ? document.model_version
            : undefined;
  const embedding =
    typeof processing.embedding_model === 'string'
      ? processing.embedding_model
      : typeof modelMetadata.embedding_model === 'string'
        ? modelMetadata.embedding_model
        : typeof provenance.embedding_model === 'string'
          ? provenance.embedding_model
          : typeof embeddingModel === 'string'
            ? embeddingModel
            : undefined;
  const state =
    typeof reparse.state === 'string'
      ? reparse.state
      : typeof document.reparse_state === 'string'
        ? document.reparse_state
        : undefined;
  const known =
    checksum ||
    deduplication ||
    parser ||
    parserVersion ||
    chunking ||
    embedding ||
    modelVersion ||
    originalAvailable !== undefined ||
    reparseAvailable !== undefined ||
    state;
  if (!known) return undefined;
  return {
    checksum,
    deduplication,
    parser,
    parserVersion,
    chunking,
    embeddingModel: embedding,
    modelVersion,
    originalAvailable,
    reparse:
      reparseAvailable !== undefined || state
        ? {
            available: Boolean(reparseAvailable),
            state: state as 'IDLE' | 'QUEUED' | 'PARSING' | 'SUCCEEDED' | 'FAILED' | undefined,
            impact: typeof reparse.impact === 'string' ? reparse.impact : undefined,
          }
        : undefined,
  };
}

function pipelineFromWire(candidate: Json, result?: Json): PipelineCandidate {
  const citations = (result?.citations as Json[] | undefined) ?? [];
  const hasEvidence = citations.length > 0;
  const preparationWire = candidate.preparation as Json | undefined;
  const preparation = preparationWire
    ? {
        state: String(preparationWire.state) as 'PREPARING' | 'READY' | 'FAILED',
        ready: Boolean(preparationWire.ready),
        error: typeof preparationWire.error === 'string' ? preparationWire.error : undefined,
        preparedAt:
          typeof preparationWire.prepared_at === 'string' ? preparationWire.prepared_at : undefined,
      }
    : undefined;
  const comparisonState = String(
    result?.candidate_state ??
      (preparation?.state === 'PREPARING' || preparation?.state === 'FAILED'
        ? preparation.state
        : hasEvidence
          ? 'READY'
          : 'NO_EVIDENCE'),
  ) as PipelineCandidate['comparisonState'];
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
    evidence: citations.map(citationFromWire),
    preparation,
    comparisonState,
    comparisonStateDetail:
      typeof result?.candidate_state_detail === 'string'
        ? result.candidate_state_detail
        : preparation?.error,
    generation: generationFromWire(result),
    runtime: runtimeFromWire(result?.retrieval_metadata as Json | undefined, candidate),
  };
}
function instanceFromWire(item: Json, detail = false): RagInstanceDetail {
  const rawDocs = (item.documents as Json[] | undefined) ?? [];
  const documents: RagDocument[] = rawDocs.map((document) => {
    const candidates = (document.candidates as Json[] | undefined) ?? [];
    const finalized = candidates.find(
      (candidate) => candidate.id === document.finalized_candidate_id,
    );
    const comparison = (document.comparison as Json | undefined) ?? {};
    const fullReindex = (document.full_reindex as Json | undefined) ?? {};
    return {
      id: String(document.id),
      name: String(document.filename),
      sourceType: String(document.content_type).includes('pdf') ? 'PDF' : 'TXT',
      status: 'PARSED',
      pipelineLabel: finalized ? pipelineFromWire(finalized).label : undefined,
      pipelineId: finalized ? String(finalized.id) : undefined,
      comparisonScope:
        document.comparison_scope === 'SAMPLE' || document.comparison_scope === 'FULL'
          ? document.comparison_scope
          : comparison.scope === 'SAMPLE' || comparison.scope === 'FULL'
            ? comparison.scope
            : undefined,
      estimatedChunkCount:
        typeof document.estimated_chunk_count === 'number'
          ? document.estimated_chunk_count
          : typeof comparison.estimated_chunk_count === 'number'
            ? comparison.estimated_chunk_count
            : undefined,
      comparisonChunkCount:
        typeof document.comparison_chunk_count === 'number'
          ? document.comparison_chunk_count
          : typeof document.selected_chunk_count === 'number'
            ? document.selected_chunk_count
            : typeof comparison.selected_chunk_count === 'number'
              ? comparison.selected_chunk_count
              : undefined,
      fullReindexRequired: fullReindex.required === true,
      fullReindexReady: fullReindex.ready === true,
      fullReindexState:
        typeof fullReindex.state === 'string'
          ? (fullReindex.state as RagProcessingJob['state'])
          : undefined,
      provenance: provenanceFromWire(document, finalized, item.embedding_model),
    };
  });
  const candidates = rawDocs.flatMap((document) =>
    ((document.candidates as Json[] | undefined) ?? []).map((candidate) =>
      pipelineFromWire(candidate),
    ),
  );
  const latestJob = jobFromWire(item.latest_job as Json | undefined);
  const needsReindex = (document: Json) => {
    const reindex = document.full_reindex as Json | undefined;
    return reindex?.required === true && typeof reindex.job_id === 'string';
  };
  const reindexDocument =
    rawDocs.find((document) => {
      const reindex = document.full_reindex as Json | undefined;
      return needsReindex(document) && reindex?.ready !== true;
    }) ?? rawDocs.find(needsReindex);
  const reindex = reindexDocument?.full_reindex as Json | undefined;
  const reindexId = typeof reindex?.job_id === 'string' ? reindex.job_id : undefined;
  const fullReindexJob =
    jobFromWire((item.pending_full_reindex_job ?? item.full_reindex_job) as Json | undefined) ??
    (reindexId && latestJob?.id === reindexId
      ? latestJob
      : reindexId
        ? {
            id: reindexId,
            state: String(reindex?.state ?? 'QUEUED') as RagProcessingJob['state'],
            currentStep: '전체 문서 색인을 준비하고 있어요.',
            completed: 0,
            total: 0,
            canRetry: false,
            canCancel: false,
            stages: [],
          }
        : undefined);
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
    fullReindexJob: detail ? fullReindexJob : undefined,
    retuningSignal: retuningSignalFromWire(item),
    candidateExploration: candidateExplorationFromWire(item),
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

function benchmarkResultFromWire(item: Json): EmbeddingBenchmarkResult {
  const numberOrNull = (value: unknown) => (typeof value === 'number' ? value : null);
  return {
    modelId: String(item.model_id),
    recallAt1: numberOrNull(item.recall_at_1),
    recallAt5: numberOrNull(item.recall_at_5),
    mrr: numberOrNull(item.mrr),
    averageLatencyMs: numberOrNull(item.average_latency_ms),
    dimension: numberOrNull(item.dimension),
    provider: String(item.provider ?? '알 수 없음'),
    status: String(item.status ?? 'UNKNOWN'),
  };
}

function benchmarkFromWire(data: Json): EmbeddingBenchmark | undefined {
  const run = data.run as Json | undefined;
  const results = data.results as Json[] | undefined;
  if (!run || !results?.length) return undefined;
  return {
    run: {
      id: String(run.id),
      corpusLabel: String(run.corpus_label ?? '우리 문서'),
      queryCount: Number(run.query_count ?? 0),
      createdAt: String(run.created_at ?? ''),
    },
    results: results.map(benchmarkResultFromWire),
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
  async latestEmbeddingBenchmark(): Promise<EmbeddingBenchmark | undefined> {
    try {
      return benchmarkFromWire(await request<Json>('/api/v1/embedding-benchmarks/latest'));
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 404) return undefined;
      fallbackOnlyWithoutApi(error);
      return undefined;
    }
  },
  async modelRuntime(): Promise<ModelServiceStatus[]> {
    try {
      const data = await request<{ services?: Json[]; items?: Json[] }>('/api/v1/model-runtime');
      return (data.services ?? data.items ?? []).map(serviceFromWire);
    } catch (error) {
      fallbackOnlyWithoutApi(error);
      await wait();
      return [
        {
          key: 'development-fallback',
          technique: 'embedding',
          modelId: '로컬 개발 fallback',
          runtime: 'development',
          status: 'NOT_CONFIGURED',
          ready: false,
          detail: '실제 임베딩 모델이 연결되지 않아 개발용 검색 fallback으로 결과를 표시합니다.',
        },
      ];
    }
  },
  async executionPlan(id: string): Promise<ExecutionPlan> {
    try {
      return planFromWire(await request<Json>(`/api/v1/rag-instances/${id}/execution-plan`));
    } catch (error) {
      fallbackOnlyWithoutApi(error);
      await wait();
      return {
        embeddingModel: 'BGE-M3',
        ready: false,
        fallbackPolicy: '개발 환경에서는 fallback이 기록됩니다.',
        requiredServices: [
          {
            key: 'development-fallback',
            technique: 'embedding',
            modelId: '로컬 개발 fallback',
            runtime: 'development',
            status: 'NOT_CONFIGURED',
            ready: false,
            detail: '실제 모델 서비스가 연결되지 않았습니다.',
          },
        ],
      };
    }
  },
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
    } catch (error) {
      fallbackOnlyWithoutApi(error);
      await wait();
      return fallbackRecommendations(questionnaire);
    }
  },
  async list(): Promise<RagInstance[]> {
    try {
      const data = await request<{ items: Json[] }>('/api/v1/rag-instances');
      return data.items.map((item) => instanceFromWire(item));
    } catch (error) {
      fallbackOnlyWithoutApi(error);
      await wait();
      return localInstances;
    }
  },
  async get(id: string): Promise<RagInstanceDetail> {
    try {
      return instanceFromWire(await request<Json>(`/api/v1/rag-instances/${id}`), true);
    } catch (error) {
      fallbackOnlyWithoutApi(error);
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
    } catch (error) {
      fallbackOnlyWithoutApi(error);
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
    } catch (error) {
      fallbackOnlyWithoutApi(error);
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
    } catch (error) {
      fallbackOnlyWithoutApi(error);
      await wait();
    }
  },
  async retryJob(jobId: string): Promise<void> {
    try {
      await request(`/api/v1/rag-jobs/${jobId}/retry`, { method: 'POST' });
    } catch (error) {
      fallbackOnlyWithoutApi(error);
      await wait();
    }
  },
  async jobs(id: string): Promise<RagProcessingJob[] | undefined> {
    try {
      const data = await request<{ items?: Json[] }>(`/api/v1/rag-instances/${id}/jobs`);
      return (data.items ?? [])
        .map(jobFromWire)
        .filter((job): job is RagProcessingJob => Boolean(job));
    } catch (error) {
      fallbackOnlyWithoutApi(error);
      // Job history is an optional operational view in mock mode.
      return undefined;
    }
  },
  async latestCandidateExploration(id: string): Promise<CandidateExploration | undefined> {
    try {
      const data = await request<{ items?: Json[] }>(
        `/api/v1/rag-instances/${id}/candidate-exploration`,
      );
      const latest = data.items?.[0];
      return latest ? candidateExplorationFromWire({ candidate_exploration: latest }) : undefined;
    } catch (error) {
      fallbackOnlyWithoutApi(error);
      return undefined;
    }
  },
  async startCandidateExploration(
    id: string,
    documentIds: string[],
    question?: string,
  ): Promise<CandidateExploration | undefined> {
    try {
      const data = await request<Json>(`/api/v1/rag-instances/${id}/candidate-exploration`, {
        method: 'POST',
        body: JSON.stringify({ document_ids: documentIds, question: question || undefined }),
      });
      return candidateExplorationFromWire(data);
    } catch (error) {
      fallbackOnlyWithoutApi(error);
      return undefined;
    }
  },
  async rollbackCandidateExploration(
    explorationId: string,
  ): Promise<CandidateExploration | undefined> {
    try {
      const data = await request<Json>(`/api/v1/candidate-exploration/${explorationId}/rollback`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      return candidateExplorationFromWire(data);
    } catch (error) {
      fallbackOnlyWithoutApi(error);
      return undefined;
    }
  },
  async restoreCandidateExploration(
    explorationId: string,
  ): Promise<CandidateExploration | undefined> {
    try {
      const data = await request<Json>(`/api/v1/candidate-exploration/${explorationId}/restore`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      return candidateExplorationFromWire(data);
    } catch (error) {
      fallbackOnlyWithoutApi(error);
      return undefined;
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
    } catch (error) {
      fallbackOnlyWithoutApi(error);
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
    } catch (error) {
      fallbackOnlyWithoutApi(error);
      await wait();
    }
  },
  async finalize(id: string, documentId: string): Promise<void> {
    try {
      await request(`/api/v1/rag-instances/${id}/tuning/finalize`, {
        method: 'POST',
        body: JSON.stringify({ document_id: documentId }),
      });
    } catch (error) {
      fallbackOnlyWithoutApi(error);
      await wait();
    }
  },
  async retune(id: string, documentIds: string[], reason?: string): Promise<RetuneStart> {
    try {
      const data = await request<Json>(`/api/v1/rag-instances/${id}/retune`, {
        method: 'POST',
        body: JSON.stringify({ document_ids: documentIds, reason }),
      });
      return {
        job: jobFromWire(data.job as Json | undefined),
        nextAction: typeof data.next_action === 'string' ? data.next_action : undefined,
      };
    } catch (error) {
      fallbackOnlyWithoutApi(error);
      await wait();
      return { nextAction: 'TUNE_DOCUMENT' };
    }
  },
  async reparseDocument(id: string, documentId: string): Promise<void> {
    try {
      await request(`/api/v1/rag-instances/${id}/documents/${documentId}/reparse`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
    } catch (error) {
      fallbackOnlyWithoutApi(error);
      await wait();
    }
  },
  async preflightSearch(id: string, documentIds: string[]): Promise<void> {
    if (!baseUrl) return;
    const query = new URLSearchParams();
    documentIds.forEach((documentId) => query.append('document_ids', documentId));
    try {
      const data = await request<Json>(
        `/api/v1/rag-instances/${id}/search/preflight?${query.toString()}`,
      );
      if (data.eligible !== true) throw preflightConflictFromPayload(data, documentIds);
    } catch (error) {
      if (error instanceof ApiRequestError && [404, 405].includes(error.status)) return;
      if (error instanceof SearchPreflightError) throw error;
      throw preflightConflict(error, documentIds);
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
        citations: citationsFromWire(data),
        latencyMs: 0,
        artifactId: String((data.artifact as Json | undefined)?.id ?? '') || undefined,
        runtime: runtimeFromWire(data.retrieval_metadata as Json | undefined, undefined),
        generation: generationFromWire(data),
        documentCoverage: coverageFromWire(data),
      };
    } catch (error) {
      fallbackOnlyWithoutApi(error);
      await wait(400);
      return {
        text: question.includes('숙박')
          ? '국내 출장 숙박비는 1박 10만원을 한도로 합니다.'
          : '해외 출장 식비는 국가 등급에 따라 하루 80~150달러입니다.',
        citations: mockRound.candidates[1].evidence,
        latencyMs: 1240,
        runtime: {
          provider: 'development-fallback',
          warning: '실제 모델 서비스가 연결되지 않아 개발용 검색 결과입니다.',
          fallback: true,
        },
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
    await this.preflightSearch(id, documentIds);
    const query = new URLSearchParams({ question, sensitivity });
    documentIds.forEach((documentId) => query.append('document_ids', documentId));
    return new Promise((resolve, reject) => {
      const source = new EventSource(
        `${baseUrl}/api/v1/rag-instances/${id}/search/stream?${query}`,
      );
      const startedAt = Date.now();
      let text = '';
      let citations: ChatAnswer['citations'] = [];
      let generation: ChatAnswer['generation'];
      let settled = false;
      const finish = (callback: () => void) => {
        if (settled) return;
        settled = true;
        source.close();
        options.signal?.removeEventListener('abort', abort);
        callback();
      };
      const abort = () =>
        finish(() =>
          reject(
            new DOMException(
              '이 화면의 답변 표시를 중단했어요. 서버 작업은 계속될 수 있어요.',
              'AbortError',
            ),
          ),
        );
      const publish = () => options.onUpdate?.({ text, citations, generation });
      const updateGeneration = (event: Event) => {
        try {
          generation = generationFromWire(JSON.parse((event as MessageEvent<string>).data) as Json);
          publish();
        } catch {
          // Generation metadata is optional; preserve the current stream state when malformed.
        }
      };
      source.addEventListener('generation', updateGeneration);
      source.addEventListener('generation_status', updateGeneration);
      source.addEventListener('status', updateGeneration);
      source.addEventListener('citations', (event) => {
        try {
          citations = (JSON.parse((event as MessageEvent<string>).data) as Json[]).map(
            citationFromWire,
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
      source.addEventListener('done', (event) =>
        finish(() => {
          let metadata: Json = {};
          try {
            metadata = JSON.parse((event as MessageEvent<string>).data) as Json;
          } catch {
            /* terminal text is still usable */
          }
          resolve({
            text,
            citations: enrichCitationDocuments(citations, metadata),
            latencyMs: Date.now() - startedAt,
            artifactId: String(metadata.artifact_id ?? '') || undefined,
            runtime: runtimeFromWire(metadata.retrieval_metadata as Json | undefined, undefined),
            generation: generationFromWire(metadata) ?? generation,
            documentCoverage: coverageFromWire(metadata),
          });
        }),
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
  async feedback(
    id: string,
    rating: 1 | -1,
    context?: { artifactId?: string; documentIds?: string[]; citationIds?: string[] },
  ): Promise<void> {
    try {
      await request(`/api/v1/rag-instances/${id}/feedback`, {
        method: 'POST',
        body: JSON.stringify({
          rating,
          artifact_id: context?.artifactId,
          document_ids: context?.documentIds,
          citation_ids: context?.citationIds,
        }),
      });
    } catch (error) {
      fallbackOnlyWithoutApi(error);
      await wait();
    }
  },
  async deleteDocument(id: string, documentId: string): Promise<void> {
    try {
      await request(`/api/v1/rag-instances/${id}/documents/${documentId}`, { method: 'DELETE' });
    } catch (error) {
      fallbackOnlyWithoutApi(error);
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
