"""FastAPI contract for the local, functional RAG Portal MVP.

The first production-shaped slice uses deterministic local parsing and lexical
retrieval. Candidate pipelines produce their own persisted chunks, so tuning
compares a real difference in retrieval context before a provider-backed
embedding/vector layer is introduced.
"""
from __future__ import annotations

from collections import Counter
import base64
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
import hashlib
import json
import os
import re
from threading import RLock
from typing import Annotated, AsyncIterator, Callable
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.state_store import StateStore
from app.document_parser import decode_source, extract_document
from app.job_queue import backend_name, dispatch, queue_observability
from app.model_runtime import execution_plan, runtime_catalog
from app.retrieval import rank as rank_segments
from app.retrieval import rerank as rerank_segments
from app.retrieval import embed
from app.generation import GenerationEndpointError, GenerationResult, generate_grounded
from app.source_storage import SourceStorageError, source_storage


API_PREFIX = "/api/v1"
STATE_STORE = StateStore(os.getenv("RAG_PORTAL_DB_PATH", ".rag-portal.sqlite3"))
STATE_LOCK = RLock()
DEFAULT_COMPARISON_CHUNK_THRESHOLD = 500
DEFAULT_MULTI_DOCUMENT_CONTEXT_LIMIT = 4
DEFAULT_MULTI_DOCUMENT_RERANK_TOP_K = 8
RETUNING_SIGNAL_VERSION = "2026-08-03.v1"
RETUNING_NEGATIVE_WEIGHT_THRESHOLD = 2.0
RETUNING_INTEGRITY_EVENT_THRESHOLD = 2
SOURCE_PROVENANCE_VERSION = "source-provenance.v1"
PARSER_PIPELINE_VERSION = "document-parser.v1"
CHUNKING_PIPELINE_VERSION = "adaptive-chunking.v1"
MODEL_PROVENANCE_VERSION = "embedding-model-contract.v1"


class InstanceStatus(StrEnum):
    SETTING_UP = "SETTING_UP"
    TUNING = "TUNING"
    READY = "READY"


class JobState(StrEnum):
    QUEUED = "QUEUED"
    PARSING = "PARSING"
    GENERATING_CANDIDATES = "GENERATING_CANDIDATES"
    INDEXING = "INDEXING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DEAD_LETTER = "DEAD_LETTER"


class CandidateState(StrEnum):
    """Readiness of one retrieval candidate and its comparison result."""

    PREPARING = "PREPARING"
    READY = "READY"
    FAILED = "FAILED"
    NO_EVIDENCE = "NO_EVIDENCE"


class Sensitivity(StrEnum):
    FLEXIBLE = "flexible"
    BALANCED = "balanced"
    STRICT = "strict"


class PipelineMode(StrEnum):
    """How a newly added source gets its retrieval pipeline."""

    REUSE = "reuse"
    RETUNE = "retune"


class ComparisonScope(StrEnum):
    """Amount of a source indexed while a user is comparing candidates."""

    FULL = "FULL"
    SAMPLE = "SAMPLE"


class JobKind(StrEnum):
    PROCESSING = "PROCESSING"
    FULL_REINDEX = "FULL_REINDEX"
    REPARSE = "REPARSE"


class ArtifactStatus(StrEnum):
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class ExplorationStatus(StrEnum):
    PROPOSED = "PROPOSED"
    ROLLED_BACK = "ROLLED_BACK"
    RESTORED = "RESTORED"


class Questionnaire(BaseModel):
    primary_language: str = "ko"
    requires_on_premise: bool = False
    budget: str = "standard"
    multi_hop_questions: bool = False
    embedding_model: str | None = None


class InstanceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    questionnaire: Questionnaire = Field(default_factory=Questionnaire)


class DocumentInput(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content: str | None = None
    content_base64: str | None = None
    content_type: str = "text/plain"


class DocumentsCreate(BaseModel):
    documents: list[DocumentInput] = Field(min_length=1)
    pipeline_mode: PipelineMode = PipelineMode.RETUNE
    reuse_from_document_id: str | None = None
    # Kept temporarily for clients that used the first MVP contract.
    reuse_finalized_pipeline: bool | None = None


class CompareRequest(BaseModel):
    document_ids: list[str] = Field(min_length=1)
    question: str = Field(min_length=1, max_length=1000)


class VoteRequest(BaseModel):
    candidate_ids: list[str] = Field(min_length=1)


class FinalizeRequest(BaseModel):
    document_id: str


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    document_ids: list[str] = Field(min_length=1)
    sensitivity: Sensitivity = Sensitivity.BALANCED
    retrieval_config: str | None = None


class FeedbackRequest(BaseModel):
    rating: Annotated[int, Field(ge=-1, le=1)]
    comment: str | None = Field(default=None, max_length=1000)
    artifact_id: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)
    category: str = Field(default="answer_quality", max_length=64)


class RetuneRequest(BaseModel):
    document_ids: list[str] = Field(min_length=1)
    reason: str | None = Field(default=None, max_length=1000)


class ReparseRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class CandidateExplorationRequest(BaseModel):
    document_ids: list[str] = Field(min_length=1)
    question: str | None = Field(default=None, max_length=1000)
    max_proposals: Annotated[int, Field(ge=1, le=6)] = 3


@dataclass
class Segment:
    id: str
    text: str
    ordinal: int
    start_offset: int
    end_offset: int


@dataclass
class Document:
    id: str
    filename: str
    content_type: str
    content: str
    segments: list[Segment]
    raw_content_base64: str | None = None
    source_metadata: dict = field(default_factory=dict)
    parser_metadata: dict = field(default_factory=dict)
    chunking_metadata: dict = field(default_factory=dict)
    model_metadata: dict = field(default_factory=dict)
    parser: str | None = None
    used_ocr: bool = False
    profile: str = "short"
    chunking_analysis: dict = field(default_factory=dict)
    parse_status: str = "PARSED"
    processing_job_id: str | None = None
    pipeline_mode: PipelineMode = PipelineMode.RETUNE
    comparison_scope: ComparisonScope = ComparisonScope.FULL
    comparison_chunk_threshold: int = DEFAULT_COMPARISON_CHUNK_THRESHOLD
    estimated_chunk_count: int = 0
    selected_chunk_count: int = 0
    candidate_chunk_counts: dict[str, int] = field(default_factory=dict)
    full_reindex_job_id: str | None = None
    full_reindex_state: JobState | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    candidate_ids: list[str] = field(default_factory=list)
    finalized_candidate_id: str | None = None


@dataclass
class Candidate:
    id: str
    document_id: str
    chunking_strategy: str
    retrieval_config: str
    friendly_name: str
    technical_description: str
    is_temporary: bool = True
    selection_count: int = 0
    finalized: bool = False
    segments: list[Segment] = field(default_factory=list)
    vectors: dict[str, list[float]] = field(default_factory=dict)
    embedding_provider: str | None = None
    embedding_dimension: int = 0
    embedding_warning: str | None = None
    chunking_parameters: dict = field(default_factory=dict)
    selection_reason: str = ""
    preparation_state: CandidateState = CandidateState.PREPARING
    preparation_error: str | None = None
    prepared_at: datetime | None = None
    estimated_chunk_count: int = 0
    selected_chunk_count: int = 0
    comparison_scope: ComparisonScope = ComparisonScope.FULL
    exploration_round_id: str | None = None
    parent_candidate_id: str | None = None
    archived: bool = False


@dataclass(frozen=True)
class ChunkingOption:
    strategy: str
    label: str
    parameters: dict
    reason: str


@dataclass
class ProcessingJob:
    id: str
    instance_id: str
    document_ids: list[str]
    state: JobState
    current_step: str
    completed_units: int
    total_units: int
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    stages: list[dict] = field(default_factory=list)
    artifact_id: str | None = None
    pipeline_mode: PipelineMode = PipelineMode.RETUNE
    reuse_source_document_id: str | None = None
    cancel_requested: bool = False
    attempt: int = 1
    kind: JobKind = JobKind.PROCESSING
    comparison_plans: dict[str, dict] = field(default_factory=dict)
    idempotency_key: str = ""
    dispatch_backend: str | None = None
    dispatch_message_id: str | None = None
    dispatch_fallback_reason: str | None = None
    execution_status: str = "IDLE"
    execution_count: int = 0
    worker_id: str | None = None
    last_heartbeat_at: datetime | None = None
    max_attempts: int = 0
    retry_backoff_seconds: int = 0
    next_attempt_at: datetime | None = None
    dead_letter_reason: str | None = None


@dataclass
class ComparisonRound:
    id: str
    instance_id: str
    document_ids: list[str]
    question: str
    candidate_ids: list[str]
    created_at: datetime
    selected_candidate_ids: list[str] = field(default_factory=list)
    candidate_states: dict[str, CandidateState] = field(default_factory=dict)


@dataclass
class CandidateExploration:
    id: str
    instance_id: str
    document_ids: list[str]
    created_at: datetime
    question: str | None = None
    max_proposals: int = 3
    status: ExplorationStatus = ExplorationStatus.PROPOSED
    candidate_pool_ids: list[str] = field(default_factory=list)
    narrowed_candidate_ids: list[str] = field(default_factory=list)
    proposals: list[dict] = field(default_factory=list)
    rationale: list[dict] = field(default_factory=list)
    ledger: list[dict] = field(default_factory=list)
    artifact_id: str | None = None


@dataclass
class RagInstance:
    id: str
    name: str
    status: InstanceStatus
    embedding_model: str
    graphrag_enabled: bool
    documents: dict[str, Document] = field(default_factory=dict)
    candidate_ids: list[str] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class Artifact:
    id: str
    instance_id: str
    type: str
    title: str
    status: ArtifactStatus
    context_document_ids: list[str]
    metadata: dict
    payload: dict
    created_at: datetime
    updated_at: datetime


INSTANCES: dict[str, RagInstance] = {}
CANDIDATES: dict[str, Candidate] = {}
JOBS: dict[str, ProcessingJob] = {}
ROUNDS: dict[str, ComparisonRound] = {}
EXPLORATIONS: dict[str, CandidateExploration] = {}
FEEDBACK: list[dict] = []
ARTIFACTS: dict[str, Artifact] = {}
BENCHMARK_RUNS: list[dict] = []


def encode_time(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def decode_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def state_payload() -> dict:
    return {
        "instances": [
            {
                "id": instance.id,
                "name": instance.name,
                "status": instance.status,
                "embedding_model": instance.embedding_model,
                "graphrag_enabled": instance.graphrag_enabled,
                "candidate_ids": instance.candidate_ids,
                "artifact_ids": instance.artifact_ids,
                "created_at": encode_time(instance.created_at),
                "documents": [
                    {
                        "id": document.id,
                        "filename": document.filename,
                        "content_type": document.content_type,
                        "content": document.content,
                        "raw_content_base64": document.raw_content_base64,
                        "source_metadata": document.source_metadata,
                        "parser_metadata": document.parser_metadata,
                        "chunking_metadata": document.chunking_metadata,
                        "model_metadata": document.model_metadata,
                        "segments": [
                            {
                                "id": segment.id,
                                "text": segment.text,
                                "ordinal": segment.ordinal,
                                "start_offset": segment.start_offset,
                                "end_offset": segment.end_offset,
                            }
                            for segment in document.segments
                        ],
                        "profile": document.profile,
                        "chunking_analysis": document.chunking_analysis,
                        "parse_status": document.parse_status,
                        "parser": document.parser,
                        "used_ocr": document.used_ocr,
                        "processing_job_id": document.processing_job_id,
                        "pipeline_mode": document.pipeline_mode,
                        "comparison_scope": document.comparison_scope,
                        "comparison_chunk_threshold": document.comparison_chunk_threshold,
                        "estimated_chunk_count": document.estimated_chunk_count,
                        "selected_chunk_count": document.selected_chunk_count,
                        "candidate_chunk_counts": document.candidate_chunk_counts,
                        "full_reindex_job_id": document.full_reindex_job_id,
                        "full_reindex_state": document.full_reindex_state,
                        "created_at": encode_time(document.created_at),
                        "candidate_ids": document.candidate_ids,
                        "finalized_candidate_id": document.finalized_candidate_id,
                    }
                    for document in instance.documents.values()
                ],
            }
            for instance in INSTANCES.values()
        ],
        "candidates": [
            {
                "id": candidate.id,
                "document_id": candidate.document_id,
                "chunking_strategy": candidate.chunking_strategy,
                "retrieval_config": candidate.retrieval_config,
                "friendly_name": candidate.friendly_name,
                "technical_description": candidate.technical_description,
                "is_temporary": candidate.is_temporary,
                "selection_count": candidate.selection_count,
                "finalized": candidate.finalized,
                "segments": [
                    {
                        "id": segment.id,
                        "text": segment.text,
                        "ordinal": segment.ordinal,
                        "start_offset": segment.start_offset,
                        "end_offset": segment.end_offset,
                    }
                    for segment in candidate.segments
                ],
                "vectors": candidate.vectors,
                "embedding_provider": candidate.embedding_provider,
                "embedding_dimension": candidate.embedding_dimension,
                "embedding_warning": candidate.embedding_warning,
                "chunking_parameters": candidate.chunking_parameters,
                "selection_reason": candidate.selection_reason,
                "preparation_state": candidate.preparation_state,
                "preparation_error": candidate.preparation_error,
                "prepared_at": encode_time(candidate.prepared_at),
                "estimated_chunk_count": candidate.estimated_chunk_count,
                "selected_chunk_count": candidate.selected_chunk_count,
                "comparison_scope": candidate.comparison_scope,
                "exploration_round_id": candidate.exploration_round_id,
                "parent_candidate_id": candidate.parent_candidate_id,
                "archived": candidate.archived,
            }
            for candidate in CANDIDATES.values()
        ],
        "jobs": [
            {
                "id": job.id,
                "instance_id": job.instance_id,
                "document_ids": job.document_ids,
                "state": job.state,
                "current_step": job.current_step,
                "completed_units": job.completed_units,
                "total_units": job.total_units,
                "created_at": encode_time(job.created_at),
                "completed_at": encode_time(job.completed_at),
                "error_message": job.error_message,
                "stages": job.stages,
                "artifact_id": job.artifact_id,
                "pipeline_mode": job.pipeline_mode,
                "reuse_source_document_id": job.reuse_source_document_id,
                "cancel_requested": job.cancel_requested,
                "attempt": job.attempt,
                "kind": job.kind,
                "comparison_plans": job.comparison_plans,
                "idempotency_key": job.idempotency_key,
                "dispatch_backend": job.dispatch_backend,
                "dispatch_message_id": job.dispatch_message_id,
                "dispatch_fallback_reason": job.dispatch_fallback_reason,
                "execution_status": job.execution_status,
                "execution_count": job.execution_count,
                "worker_id": job.worker_id,
                "last_heartbeat_at": encode_time(job.last_heartbeat_at),
                "max_attempts": job.max_attempts,
                "retry_backoff_seconds": job.retry_backoff_seconds,
                "next_attempt_at": encode_time(job.next_attempt_at),
                "dead_letter_reason": job.dead_letter_reason,
            }
            for job in JOBS.values()
        ],
        "rounds": [
            {
                "id": round_.id,
                "instance_id": round_.instance_id,
                "document_ids": round_.document_ids,
                "question": round_.question,
                "candidate_ids": round_.candidate_ids,
                "created_at": encode_time(round_.created_at),
                "selected_candidate_ids": round_.selected_candidate_ids,
                "candidate_states": round_.candidate_states,
            }
            for round_ in ROUNDS.values()
        ],
        "candidate_explorations": [
            {
                "id": exploration.id,
                "instance_id": exploration.instance_id,
                "document_ids": exploration.document_ids,
                "created_at": encode_time(exploration.created_at),
                "question": exploration.question,
                "max_proposals": exploration.max_proposals,
                "status": exploration.status,
                "candidate_pool_ids": exploration.candidate_pool_ids,
                "narrowed_candidate_ids": exploration.narrowed_candidate_ids,
                "proposals": exploration.proposals,
                "rationale": exploration.rationale,
                "ledger": exploration.ledger,
                "artifact_id": exploration.artifact_id,
            }
            for exploration in EXPLORATIONS.values()
        ],
        "artifacts": [
            {
                "id": artifact.id,
                "instance_id": artifact.instance_id,
                "type": artifact.type,
                "title": artifact.title,
                "status": artifact.status,
                "context_document_ids": artifact.context_document_ids,
                "metadata": artifact.metadata,
                "payload": artifact.payload,
                "created_at": encode_time(artifact.created_at),
                "updated_at": encode_time(artifact.updated_at),
            }
            for artifact in ARTIFACTS.values()
        ],
        "feedback": FEEDBACK,
        "benchmark_runs": BENCHMARK_RUNS,
    }


def persist_state() -> None:
    with STATE_LOCK:
        STATE_STORE.save(state_payload())


def restore_state() -> None:
    payload = STATE_STORE.load()
    if not payload:
        return
    with STATE_LOCK:
        INSTANCES.clear()
        CANDIDATES.clear()
        JOBS.clear()
        ROUNDS.clear()
        EXPLORATIONS.clear()
        ARTIFACTS.clear()
        FEEDBACK.clear()
        BENCHMARK_RUNS.clear()
        for item in payload.get("instances", []):
            instance = RagInstance(
                id=item["id"],
                name=item["name"],
                status=InstanceStatus(item["status"]),
                embedding_model=item["embedding_model"],
                graphrag_enabled=item["graphrag_enabled"],
                candidate_ids=item.get("candidate_ids", []),
                artifact_ids=item.get("artifact_ids", []),
                created_at=decode_time(item.get("created_at")) or datetime.now(UTC),
            )
            for raw_document in item.get("documents", []):
                document = Document(
                    id=raw_document["id"],
                    filename=raw_document["filename"],
                    content_type=raw_document["content_type"],
                    content=raw_document["content"],
                    segments=[Segment(**segment) for segment in raw_document.get("segments", [])],
                    raw_content_base64=raw_document.get("raw_content_base64"),
                    source_metadata=raw_document.get("source_metadata", {}),
                    parser_metadata=raw_document.get("parser_metadata", {}),
                    chunking_metadata=raw_document.get("chunking_metadata", {}),
                    model_metadata=raw_document.get("model_metadata", {}),
                    profile=raw_document.get("profile", "short"),
                    chunking_analysis=raw_document.get("chunking_analysis", {}),
                    parse_status=raw_document.get("parse_status", "UPLOADED"),
                    parser=raw_document.get("parser"),
                    used_ocr=raw_document.get("used_ocr", False),
                    processing_job_id=raw_document.get("processing_job_id"),
                    pipeline_mode=PipelineMode(raw_document.get("pipeline_mode", PipelineMode.RETUNE)),
                    comparison_scope=ComparisonScope(raw_document.get("comparison_scope", ComparisonScope.FULL)),
                    comparison_chunk_threshold=raw_document.get("comparison_chunk_threshold", DEFAULT_COMPARISON_CHUNK_THRESHOLD),
                    estimated_chunk_count=raw_document.get("estimated_chunk_count", 0),
                    selected_chunk_count=raw_document.get("selected_chunk_count", 0),
                    candidate_chunk_counts=raw_document.get("candidate_chunk_counts", {}),
                    full_reindex_job_id=raw_document.get("full_reindex_job_id"),
                    full_reindex_state=JobState(raw_document["full_reindex_state"]) if raw_document.get("full_reindex_state") else None,
                    created_at=decode_time(raw_document.get("created_at")) or datetime.now(UTC),
                    candidate_ids=raw_document.get("candidate_ids", []),
                    finalized_candidate_id=raw_document.get("finalized_candidate_id"),
                )
                instance.documents[document.id] = document
            INSTANCES[instance.id] = instance
        for item in payload.get("candidates", []):
            legacy_state = CandidateState.READY if item.get("vectors") else CandidateState.PREPARING
            CANDIDATES[item["id"]] = Candidate(
                **{
                    **item,
                    "segments": [Segment(**segment) for segment in item.get("segments", [])],
                    "vectors": item.get("vectors", {}),
                    "preparation_state": CandidateState(item.get("preparation_state", legacy_state)),
                    "prepared_at": decode_time(item.get("prepared_at")),
                    "comparison_scope": ComparisonScope(item.get("comparison_scope", ComparisonScope.FULL)),
                    "exploration_round_id": item.get("exploration_round_id"),
                    "parent_candidate_id": item.get("parent_candidate_id"),
                    "archived": item.get("archived", False),
                }
            )
        documents_by_id = {
            document.id: document
            for instance in INSTANCES.values()
            for document in instance.documents.values()
        }
        # Snapshots written before candidate chunks existed remain usable after
        # the upgrade; the source text is still the canonical input.
        for candidate in CANDIDATES.values():
            if not candidate.segments and (document := documents_by_id.get(candidate.document_id)):
                candidate.segments = chunks_for_strategy(document, candidate.chunking_strategy)
        for item in payload.get("jobs", []):
            JOBS[item["id"]] = ProcessingJob(
                id=item["id"],
                instance_id=item["instance_id"],
                document_ids=item.get("document_ids", []),
                state=JobState(item["state"]),
                current_step=item["current_step"],
                completed_units=item["completed_units"],
                total_units=item["total_units"],
                created_at=decode_time(item.get("created_at")) or datetime.now(UTC),
                completed_at=decode_time(item.get("completed_at")),
                error_message=item.get("error_message"),
                stages=item.get("stages", []),
                artifact_id=item.get("artifact_id"),
                pipeline_mode=PipelineMode(item.get("pipeline_mode", PipelineMode.RETUNE)),
                reuse_source_document_id=item.get("reuse_source_document_id"),
                cancel_requested=item.get("cancel_requested", False),
                attempt=item.get("attempt", 1),
                kind=JobKind(item.get("kind", JobKind.PROCESSING)),
                comparison_plans=item.get("comparison_plans", {}),
                idempotency_key=item.get("idempotency_key", ""),
                dispatch_backend=item.get("dispatch_backend"),
                dispatch_message_id=item.get("dispatch_message_id"),
                dispatch_fallback_reason=item.get("dispatch_fallback_reason"),
                # A process restart has no active worker lease; pending jobs are
                # safely reclaimed through their durable idempotency key.
                execution_status="IDLE" if JobState(item["state"]) in {JobState.QUEUED, JobState.PARSING, JobState.GENERATING_CANDIDATES, JobState.INDEXING} else item.get("execution_status", "IDLE"),
                execution_count=item.get("execution_count", 0),
                worker_id=item.get("worker_id"),
                last_heartbeat_at=decode_time(item.get("last_heartbeat_at")),
                max_attempts=item.get("max_attempts", job_max_attempts()),
                retry_backoff_seconds=item.get("retry_backoff_seconds", job_retry_backoff_seconds()),
                next_attempt_at=decode_time(item.get("next_attempt_at")),
                dead_letter_reason=item.get("dead_letter_reason"),
            )
        for item in payload.get("rounds", []):
            ROUNDS[item["id"]] = ComparisonRound(
                id=item["id"],
                instance_id=item["instance_id"],
                document_ids=item.get("document_ids", []),
                question=item["question"],
                candidate_ids=item.get("candidate_ids", []),
                created_at=decode_time(item.get("created_at")) or datetime.now(UTC),
                selected_candidate_ids=item.get("selected_candidate_ids", []),
                candidate_states={
                    candidate_id: CandidateState(state)
                    for candidate_id, state in item.get("candidate_states", {}).items()
                },
            )
        for item in payload.get("candidate_explorations", []):
            EXPLORATIONS[item["id"]] = CandidateExploration(
                id=item["id"],
                instance_id=item["instance_id"],
                document_ids=item.get("document_ids", []),
                created_at=decode_time(item.get("created_at")) or datetime.now(UTC),
                question=item.get("question"),
                max_proposals=item.get("max_proposals", 3),
                status=ExplorationStatus(item.get("status", ExplorationStatus.PROPOSED)),
                candidate_pool_ids=item.get("candidate_pool_ids", []),
                narrowed_candidate_ids=item.get("narrowed_candidate_ids", []),
                proposals=item.get("proposals", []),
                rationale=item.get("rationale", []),
                ledger=item.get("ledger", []),
                artifact_id=item.get("artifact_id"),
            )
        for item in payload.get("artifacts", []):
            ARTIFACTS[item["id"]] = Artifact(
                id=item["id"],
                instance_id=item["instance_id"],
                type=item["type"],
                title=item["title"],
                status=ArtifactStatus(item["status"]),
                context_document_ids=item.get("context_document_ids", []),
                metadata=item.get("metadata", {}),
                payload=item.get("payload", {}),
                created_at=decode_time(item.get("created_at")) or datetime.now(UTC),
                updated_at=decode_time(item.get("updated_at")) or datetime.now(UTC),
            )
        FEEDBACK.extend(payload.get("feedback", []))
        BENCHMARK_RUNS.extend(payload.get("benchmark_runs", []))


def now() -> str:
    return datetime.now(UTC).isoformat()


def new_id() -> str:
    return str(uuid4())


def source_key_for(instance_id: str, checksum_sha256: str) -> str:
    return f"instances/{instance_id}/sources/{checksum_sha256}"


def store_document_source(instance: RagInstance, document: Document, data: bytes) -> None:
    checksum = hashlib.sha256(data).hexdigest()
    prior = next(
        (
            item
            for item in instance.documents.values()
            if item.id != document.id and item.source_metadata.get("checksum_sha256") == checksum
        ),
        None,
    )
    key = source_key_for(instance.id, checksum)
    stored = source_storage().put_if_absent(key, data)
    document.source_metadata = {
        "version": SOURCE_PROVENANCE_VERSION,
        "checksum_algorithm": "sha256",
        "checksum_sha256": checksum,
        "size_bytes": len(data),
        "storage_backend": stored.backend,
        "storage_key": stored.key,
        "deduplication": {
            "scope": "INSTANCE",
            "policy": "REUSE_EXISTING_SOURCE_OBJECT",
            "status": "DEDUPLICATED" if prior or not stored.created else "STORED",
            "deduplicated_from_document_id": prior.id if prior else None,
        },
        "stored_at": now(),
    }


def source_data_for(document: Document) -> bytes:
    metadata = document.source_metadata
    if metadata.get("storage_key"):
        return source_storage().get(metadata["storage_key"])
    # Legacy snapshots retain inline source content; make its non-reproducible
    # status explicit until a new upload/reparse source object is created.
    return decode_source(document.content, document.raw_content_base64)


def parse_document_from_stored_source(instance: RagInstance, document: Document) -> None:
    data = source_data_for(document)
    parsed = extract_document(
        filename=document.filename,
        content_type=document.content_type,
        content=None,
        content_base64=base64.b64encode(data).decode("ascii"),
    )
    document.content = parsed.text
    document.parser = parsed.parser
    document.used_ocr = parsed.used_ocr
    document.segments = split_segments(parsed.text)
    document.chunking_analysis = analyze_document_for_chunking(document)
    document.profile = document_profile(document, document.chunking_analysis)
    configure_comparison_scope(document)
    previous_revision = int(document.parser_metadata.get("parse_revision", 0))
    document.parser_metadata = {
        "version": PARSER_PIPELINE_VERSION,
        "parser": parsed.parser,
        "used_ocr": parsed.used_ocr,
        "warnings": parsed.warnings,
        "parse_revision": previous_revision + 1,
        "parsed_at": now(),
    }
    document.chunking_metadata = {
        "version": CHUNKING_PIPELINE_VERSION,
        "profile": document.profile,
        "analysis": document.chunking_analysis,
        "comparison_scope": document.comparison_scope,
        "comparison_chunk_threshold": document.comparison_chunk_threshold,
        "estimated_chunk_count": document.estimated_chunk_count,
        "selected_chunk_count": document.selected_chunk_count,
    }
    document.parse_status = "PARSED"


def not_found(resource: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"{resource}을(를) 찾을 수 없습니다."})


def get_instance(instance_id: str) -> RagInstance:
    instance = INSTANCES.get(instance_id)
    if not instance:
        raise not_found("RAG 인스턴스")
    return instance


def recommend_embedding(questionnaire: Questionnaire) -> str:
    model_ids = {item["id"] for item in embedding_recommendations(questionnaire)}
    if questionnaire.embedding_model in model_ids:
        return questionnaire.embedding_model
    return embedding_recommendations(questionnaire)[0]["id"]


def embedding_recommendations(questionnaire: Questionnaire) -> list[dict[str, str | bool]]:
    """Return a small, explainable candidate set before one model is fixed per instance."""
    korean_first = questionnaire.primary_language.lower() in {"ko", "korean", "한국어", "multilingual"}
    low_budget = questionnaire.budget.lower() in {"low", "free", "낮음"}
    choices = [
        {
            "id": "BGE-M3",
            "label": "균형형 다국어 검색",
            "reason": "한국어·영어가 섞인 문서와 하이브리드 검색을 폭넓게 다룰 수 있어요.",
            "tradeoff": "가벼운 모델보다 운영 자원이 더 필요할 수 있어요.",
            "score": 4 + (3 if korean_first else 0) + (1 if questionnaire.multi_hop_questions else 0),
        },
        {
            "id": "Qwen3-Embedding-0.6B",
            "label": "자체 운영 우선",
            "reason": "상대적으로 가벼워 사내·폐쇄망 환경에서 시작하기 좋습니다.",
            "tradeoff": "복잡한 다국어 의미 검색은 균형형 후보와 실측 비교가 필요해요.",
            "score": 3 + (5 if questionnaire.requires_on_premise else 0) + (2 if low_budget else 0),
        },
        {
            "id": "EmbeddingGemma-300M",
            "label": "경량 운영형",
            "reason": "작은 운영 비용으로 빠르게 기준선을 만들고 싶을 때 적합합니다.",
            "tradeoff": "난도가 높은 문서에서는 실제 문서 벤치마크로 품질을 확인해야 해요.",
            "score": 2 + (5 if low_budget else 0) + (1 if questionnaire.requires_on_premise else 0),
        },
    ]
    ranked = sorted(choices, key=lambda choice: int(choice["score"]), reverse=True)
    return [
        {key: value for key, value in choice.items() if key != "score"} | {"recommended": index == 0}
        for index, choice in enumerate(ranked)
    ]


def split_segments(content: str) -> list[Segment]:
    """Stable parser mock: preserve paragraph/heading evidence for citations."""
    pieces = [p.strip() for p in re.split(r"\n\s*\n|(?<=\.)\s+(?=[A-Z가-힣제])", content) if p.strip()]
    if not pieces:
        pieces = [content.strip()]
    cursor = 0
    segments = []
    for index, piece in enumerate(pieces):
        start_offset = content.find(piece, cursor)
        # The split source is always the same input, but this keeps duplicate
        # paragraphs navigable by searching after the prior match.
        if start_offset < 0:
            start_offset = cursor
        end_offset = start_offset + len(piece)
        segments.append(Segment(id=new_id(), text=piece, ordinal=index + 1, start_offset=start_offset, end_offset=end_offset))
        cursor = end_offset
    return segments


HEADING_PATTERN = re.compile(r"(?m)^(?:#{1,6}\s+|제\s*\d+\s*(?:조|장)|chapter\b)", re.IGNORECASE)


def clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(value, upper))


def analyze_document_for_chunking(document: Document) -> dict:
    """Measure source shape before choosing a bounded candidate set.

    The measurements are persisted so a user can understand why candidate
    parameters differ for a table, a policy document, or OCR output.
    """
    content = document.content
    lines = [line for line in content.splitlines() if line.strip()]
    paragraphs = [paragraph for paragraph in re.split(r"\n\s*\n", content) if paragraph.strip()]
    heading_count = len(HEADING_PATTERN.findall(content))
    table_like_lines = sum(1 for line in lines if line.count("|") >= 1 or line.count(",") >= 2 or line.count("\t") >= 1)
    table_ratio = table_like_lines / len(lines) if lines else 0.0
    average_paragraph_chars = round(sum(len(paragraph.strip()) for paragraph in paragraphs) / len(paragraphs)) if paragraphs else len(content)
    return {
        "character_count": len(content),
        "line_count": len(lines),
        "paragraph_count": len(paragraphs),
        "heading_count": heading_count,
        "table_like_line_count": table_like_lines,
        "table_line_ratio": round(table_ratio, 3),
        "average_paragraph_chars": average_paragraph_chars,
        "used_ocr": document.used_ocr,
    }


def document_profile(document: Document, analysis: dict | None = None) -> str:
    analysis = analysis or analyze_document_for_chunking(document)
    if document.used_ocr:
        return "scanned"
    if document.filename.lower().endswith((".csv", ".xlsx", ".xls")) or (
        analysis["table_like_line_count"] >= 2 and analysis["table_line_ratio"] >= 0.35
    ):
        return "table"
    if analysis["heading_count"] >= 2:
        return "structured"
    if analysis["character_count"] >= 6000 or analysis["paragraph_count"] >= 16:
        return "long"
    return "short"


def make_chunk(content: str, start_offset: int, end_offset: int, ordinal: int) -> Segment | None:
    """Create a citation-ready chunk without losing its position in the source."""
    raw = content[start_offset:end_offset]
    leading = len(raw) - len(raw.lstrip())
    trailing = len(raw) - len(raw.rstrip())
    start_offset += leading
    end_offset -= trailing
    if start_offset >= end_offset:
        return None
    return Segment(
        id=new_id(),
        text=content[start_offset:end_offset],
        ordinal=ordinal,
        start_offset=start_offset,
        end_offset=end_offset,
    )


def fixed_chunks(
    document: Document,
    width: int = 360,
    overlap: int = 48,
    *,
    start_offset: int = 0,
    end_offset: int | None = None,
    ordinal_start: int = 1,
) -> list[Segment]:
    chunks: list[Segment] = []
    cursor = start_offset
    content = document.content
    limit = end_offset if end_offset is not None else len(content)
    while cursor < limit:
        end = min(limit, cursor + width)
        if end < limit:
            boundary = max(content.rfind("\n", cursor + 120, end), content.rfind(" ", cursor + 120, end))
            if boundary > cursor:
                end = boundary + 1
        chunk = make_chunk(content, cursor, end, ordinal_start + len(chunks))
        if chunk:
            chunks.append(chunk)
        if end >= limit:
            break
        cursor = max(end - overlap, cursor + 1)
    return chunks


def grouped_source_chunks(document: Document, target_size: int = 520) -> list[Segment]:
    """Keep nearby parsed units together while respecting paragraphs and headings."""
    chunks: list[Segment] = []
    group_start: int | None = None
    group_end: int | None = None
    for source in document.segments:
        if group_start is None:
            group_start, group_end = source.start_offset, source.end_offset
            continue
        assert group_end is not None
        if source.end_offset - group_start > target_size:
            chunk = make_chunk(document.content, group_start, group_end, len(chunks) + 1)
            if chunk:
                chunks.append(chunk)
            group_start, group_end = source.start_offset, source.end_offset
        else:
            group_end = source.end_offset
    if group_start is not None and group_end is not None:
        chunk = make_chunk(document.content, group_start, group_end, len(chunks) + 1)
        if chunk:
            chunks.append(chunk)
    return chunks


def structured_chunks(document: Document, max_section_chars: int = 1200, overlap: int = 80) -> list[Segment]:
    markers = list(re.finditer(r"(?m)^(?=(?:#{1,6}\s+|제\s*\d+\s*(?:조|장)|chapter\b))", document.content, re.IGNORECASE))
    if len(markers) < 2:
        return grouped_source_chunks(document, target_size=max_section_chars)
    chunks: list[Segment] = []
    starts = [marker.start() for marker in markers]
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(document.content)
        if end - start > max_section_chars:
            chunks.extend(
                fixed_chunks(
                    document,
                    width=max_section_chars,
                    overlap=overlap,
                    start_offset=start,
                    end_offset=end,
                    ordinal_start=len(chunks) + 1,
                )
            )
        else:
            chunk = make_chunk(document.content, start, end, len(chunks) + 1)
            if chunk:
                chunks.append(chunk)
    return chunks


def table_chunks(document: Document, rows_per_chunk: int = 6) -> list[Segment]:
    lines = list(re.finditer(r"(?m)^.*\S.*$", document.content))
    if len(lines) < 2:
        return grouped_source_chunks(document)
    chunks: list[Segment] = []
    header = lines[0]
    for start_index in range(1, len(lines), rows_per_chunk):
        rows = lines[start_index : start_index + rows_per_chunk]
        chunk = make_chunk(document.content, header.start(), rows[-1].end(), len(chunks) + 1)
        if chunk:
            chunks.append(chunk)
    return chunks


def chunks_for_strategy(document: Document, strategy: str, parameters: dict | None = None) -> list[Segment]:
    parameters = parameters or {}
    if strategy == "document":
        chunk = make_chunk(document.content, 0, len(document.content), 1)
        return [chunk] if chunk else []
    if strategy == "fixed":
        return fixed_chunks(document, width=int(parameters.get("width_chars", 360)), overlap=int(parameters.get("overlap_chars", 48)))
    if strategy in {"hierarchical", "ocr_hierarchical"}:
        return structured_chunks(
            document,
            max_section_chars=int(parameters.get("max_section_chars", 1200)),
            overlap=int(parameters.get("overlap_chars", 80)),
        )
    if strategy == "table":
        return table_chunks(document, rows_per_chunk=int(parameters.get("rows_per_chunk", 6)))
    return grouped_source_chunks(document, target_size=int(parameters.get("target_chars", 520)))


def adaptive_chunking_options(document: Document) -> list[ChunkingOption]:
    analysis = document.chunking_analysis or analyze_document_for_chunking(document)
    profile = document.profile or document_profile(document, analysis)
    content_length = analysis["character_count"]
    average_paragraph = analysis["average_paragraph_chars"]
    fixed_width = clamp(max(320, average_paragraph * 3), 320, 900)
    fixed_overlap = clamp(round(fixed_width * (0.12 if profile in {"long", "scanned"} else 0.1)), 36, 120)
    semantic_target = clamp(max(420, average_paragraph * 4), 420, 1100)
    structured_target = clamp(max(800, average_paragraph * 6), 800, 1800)
    table_rows = clamp(round(analysis["line_count"] / 8), 3, 10)

    if profile == "table":
        return [
            ChunkingOption("table", "표 중심", {"rows_per_chunk": table_rows, "repeat_header": True}, f"표 형태 행 비율 {analysis['table_line_ratio']:.0%}에 맞춰 헤더를 반복하고 {table_rows}행씩 묶습니다."),
            ChunkingOption("hierarchical", "구조 보존", {"max_section_chars": structured_target, "overlap_chars": fixed_overlap}, "시트·표 외 설명 문단도 함께 검색할 수 있도록 구조 단위 후보를 둡니다."),
            ChunkingOption("fixed", "재현율 기준", {"width_chars": fixed_width, "overlap_chars": fixed_overlap}, "열 경계가 불규칙한 셀 값도 놓치지 않도록 겹침 있는 고정 길이 기준선을 둡니다."),
        ]
    if profile == "structured":
        return [
            ChunkingOption("hierarchical", "구조 중심", {"max_section_chars": structured_target, "overlap_chars": fixed_overlap, "preserve_heading": True}, f"제목 {analysis['heading_count']}개를 경계로 사용하고 긴 절은 최대 {structured_target}자로 나눕니다."),
            ChunkingOption("semantic", "문단 의미 중심", {"target_chars": semantic_target}, f"평균 문단 {average_paragraph}자를 기준으로 인접 문단을 약 {semantic_target}자까지 묶습니다."),
            ChunkingOption("fixed", "재현율 기준", {"width_chars": fixed_width, "overlap_chars": fixed_overlap}, "절 경계가 고르지 않은 경우를 검증하는 겹침 고정 길이 후보입니다."),
        ]
    if profile == "long":
        return [
            ChunkingOption("semantic", "문단 의미 중심", {"target_chars": semantic_target}, f"{analysis['paragraph_count']}개 문단을 평균 {average_paragraph}자 단위로 묶어 문맥을 유지합니다."),
            ChunkingOption("fixed", "긴 문서 재현율", {"width_chars": fixed_width, "overlap_chars": fixed_overlap}, f"{content_length}자 장문에서 인접 근거를 잃지 않도록 {fixed_overlap}자 겹침을 둡니다."),
            ChunkingOption("hierarchical", "완화된 구조 중심", {"max_section_chars": structured_target, "overlap_chars": fixed_overlap}, "약한 제목 구조도 활용하는 보조 후보입니다."),
        ]
    if profile == "scanned":
        ocr_target = clamp(round(semantic_target * 0.78), 320, 780)
        return [
            ChunkingOption("ocr_hierarchical", "OCR 구조 중심", {"max_section_chars": ocr_target, "overlap_chars": fixed_overlap}, f"OCR 인식 오차를 줄이기 위해 구조 단위를 최대 {ocr_target}자로 작게 유지합니다."),
            ChunkingOption("ocr_semantic", "OCR 문단 중심", {"target_chars": ocr_target}, "OCR로 복원된 문단의 문맥을 유지하는 후보입니다."),
            ChunkingOption("fixed", "OCR 재현율", {"width_chars": clamp(fixed_width, 300, 680), "overlap_chars": fixed_overlap}, "인식된 줄 경계가 불안정한 경우를 위한 겹침 기준선입니다."),
        ]
    return [
        ChunkingOption("document", "문서 단위", {"max_document_chars": 1800}, f"{content_length}자 짧은 문서는 분할 손실을 확인하기 위해 전체 문맥 후보를 둡니다."),
        ChunkingOption("semantic", "주제 단위", {"target_chars": semantic_target}, f"평균 문단 {average_paragraph}자를 기준으로 필요한 문단만 묶습니다."),
        ChunkingOption("fixed", "기본 길이", {"width_chars": fixed_width, "overlap_chars": fixed_overlap}, "짧은 문서에서도 특정 문장 위치를 확인하는 비교 기준선입니다."),
    ]


def candidate_blueprints(document: Document) -> list[tuple[ChunkingOption, str, str]]:
    variable = "BM25" if document.profile == "table" else "Dense"
    retrievals = [("일반 검색", "hybrid"), ("정밀 검색", "hybrid_rerank"), ("용어 검색" if variable == "BM25" else "의미 검색", variable.lower())]
    return [
        (chunker, retrieval_label, retrieval_key)
        for chunker in adaptive_chunking_options(document)
        for retrieval_label, retrieval_key in retrievals
    ]


def comparison_chunk_threshold() -> int:
    """Read the per-candidate comparison budget without hard-coding policy."""
    try:
        return max(1, int(os.getenv("RAG_PORTAL_COMPARISON_CHUNK_THRESHOLD", str(DEFAULT_COMPARISON_CHUNK_THRESHOLD))))
    except ValueError:
        return DEFAULT_COMPARISON_CHUNK_THRESHOLD


def evenly_sample_segments(segments: list[Segment], limit: int) -> list[Segment]:
    """Keep sample comparison bounded while covering the entire source span."""
    if len(segments) <= limit:
        return segments
    if limit == 1:
        return [segments[0]]
    indexes = {
        round(index * (len(segments) - 1) / (limit - 1))
        for index in range(limit)
    }
    return [segment for index, segment in enumerate(segments) if index in indexes]


def configure_comparison_scope(document: Document) -> None:
    """Persist the full-size estimate and the bounded tuning input for a source.

    The threshold is evaluated per chunking strategy. Retrieval variants do not
    change embedding cost, so they share their strategy's selected chunks.
    """
    threshold = comparison_chunk_threshold()
    options = adaptive_chunking_options(document)
    counts = {
        option.strategy: len(chunks_for_strategy(document, option.strategy, option.parameters))
        for option in options
    }
    estimated = max(counts.values(), default=0)
    document.comparison_chunk_threshold = threshold
    document.candidate_chunk_counts = counts
    document.estimated_chunk_count = estimated
    document.comparison_scope = (
        ComparisonScope.SAMPLE
        if document.pipeline_mode == PipelineMode.RETUNE and estimated > threshold
        else ComparisonScope.FULL
    )
    document.selected_chunk_count = min(estimated, threshold) if document.comparison_scope == ComparisonScope.SAMPLE else estimated


def candidate_comparison_segments(document: Document, option: ChunkingOption) -> tuple[list[Segment], int]:
    full_segments = chunks_for_strategy(document, option.strategy, option.parameters)
    selected = (
        evenly_sample_segments(full_segments, document.comparison_chunk_threshold)
        if document.comparison_scope == ComparisonScope.SAMPLE
        else full_segments
    )
    return selected, len(full_segments)


def create_candidates(instance: RagInstance, document: Document) -> list[Candidate]:
    if not document.candidate_chunk_counts:
        configure_comparison_scope(document)
    candidates = []
    for chunker, retrieval_label, retrieval_key in candidate_blueprints(document):
        segments, estimated_chunk_count = candidate_comparison_segments(document, chunker)
        candidate = Candidate(
            id=new_id(),
            document_id=document.id,
            chunking_strategy=chunker.strategy,
            retrieval_config=retrieval_key,
            friendly_name=f"{chunker.label} + {retrieval_label}",
            technical_description=f"{chunker.reason} · {chunker.strategy} + {retrieval_key}",
            chunking_parameters=chunker.parameters,
            selection_reason=chunker.reason,
            segments=segments,
            estimated_chunk_count=estimated_chunk_count,
            selected_chunk_count=len(segments),
            comparison_scope=document.comparison_scope,
        )
        CANDIDATES[candidate.id] = candidate
        candidates.append(candidate)
        document.candidate_ids.append(candidate.id)
        instance.candidate_ids.append(candidate.id)
    return candidates


def exploration_signals(candidate: Candidate) -> dict:
    """Bounded, explainable operational evidence; never a quality score."""
    observed_states = [
        round_.candidate_states.get(candidate.id)
        for round_ in ROUNDS.values()
        if candidate.id in round_.candidate_ids and candidate.id in round_.candidate_states
    ]
    ready_evidence = sum(state == CandidateState.READY for state in observed_states)
    no_evidence = sum(state == CandidateState.NO_EVIDENCE for state in observed_states)
    prepared = candidate.preparation_state == CandidateState.READY
    priority = (100 if prepared else 0) + (candidate.selection_count * 10) + (ready_evidence * 4) - (no_evidence * 3)
    return {
        "prepared": prepared,
        "preparation_state": candidate.preparation_state,
        "selection_count": candidate.selection_count,
        "ready_evidence_count": ready_evidence,
        "no_evidence_count": no_evidence,
        "vector_count": len(candidate.vectors),
        "priority": priority,
        "interpretation": "작업 준비 상태·사용자 투표·비교 근거의 제한된 관측값입니다. 품질 점수 또는 자동 선택 근거가 아닙니다.",
    }


def exploration_variant(candidate: Candidate) -> tuple[dict, str, str]:
    parameters = dict(candidate.chunking_parameters)
    if candidate.chunking_strategy == "fixed":
        parameters["width_chars"] = clamp(round(int(parameters.get("width_chars", 360)) * 0.82), 240, 1000)
        parameters["overlap_chars"] = clamp(round(int(parameters.get("overlap_chars", 48)) * 1.2), 24, 160)
        chunking_reason = "더 작은 창과 약간 큰 겹침으로 인접 근거 회수 여부를 확인합니다."
    elif candidate.chunking_strategy in {"hierarchical", "ocr_hierarchical"}:
        parameters["max_section_chars"] = clamp(round(int(parameters.get("max_section_chars", 1200)) * 0.8), 500, 2000)
        parameters["overlap_chars"] = clamp(round(int(parameters.get("overlap_chars", 80)) * 1.15), 24, 180)
        chunking_reason = "구조 단위를 더 촘촘하게 나눠 절 경계의 영향만 비교합니다."
    elif candidate.chunking_strategy == "table":
        parameters["rows_per_chunk"] = clamp(int(parameters.get("rows_per_chunk", 6)) - 1, 2, 12)
        chunking_reason = "표 행 묶음을 줄여 행 단위 근거 회수 여부를 확인합니다."
    else:
        parameters["target_chars"] = clamp(round(int(parameters.get("target_chars", 520)) * 0.85), 320, 1200)
        chunking_reason = "묶음 크기를 조정해 근거 밀도를 비교합니다."
    retrieval = {
        "bm25": "hybrid",
        "dense": "hybrid_rerank",
        "hybrid": "hybrid_rerank",
        "hybrid_rerank": "hybrid",
    }.get(candidate.retrieval_config, "hybrid")
    return parameters, retrieval, chunking_reason


def create_exploration_candidate(instance: RagInstance, document: Document, proposal: dict, exploration_id: str) -> Candidate:
    parameters = proposal["chunking_parameters"]
    full_segments = chunks_for_strategy(document, proposal["chunking_strategy"], parameters)
    # Exploration is still a comparison activity. Reusing the documented
    # bounded-sample rule prevents a small proposal budget from silently
    # embedding an unbounded large source before explicit finalization.
    segments = (
        evenly_sample_segments(full_segments, document.comparison_chunk_threshold)
        if document.comparison_scope == ComparisonScope.SAMPLE
        else full_segments
    )
    candidate = Candidate(
        id=new_id(),
        document_id=document.id,
        chunking_strategy=proposal["chunking_strategy"],
        retrieval_config=proposal["retrieval_config"],
        friendly_name=f"탐색 제안 · {proposal['base_friendly_name']}",
        technical_description=proposal["technical_description"],
        chunking_parameters=parameters,
        selection_reason=proposal["selection_reason"],
        segments=segments,
        estimated_chunk_count=len(full_segments),
        selected_chunk_count=len(segments),
        comparison_scope=document.comparison_scope,
        exploration_round_id=exploration_id,
        parent_candidate_id=proposal["parent_candidate_id"],
    )
    # Register before indexing so model provenance accurately includes the
    # retrieval configuration being prepared, just like the normal candidate
    # creation path.
    CANDIDATES[candidate.id] = candidate
    document.candidate_ids.append(candidate.id)
    instance.candidate_ids.append(candidate.id)
    try:
        candidate.preparation_state = CandidateState.PREPARING
        prepare_candidate_index(instance, candidate)
    except Exception as error:
        candidate.preparation_state = CandidateState.FAILED
        candidate.preparation_error = str(error)
    else:
        candidate.preparation_state = CandidateState.READY
        candidate.prepared_at = datetime.now(UTC)
    proposal["candidate_id"] = candidate.id
    proposal["candidate_state"] = candidate.preparation_state
    return candidate


def prepare_candidate_index(instance: RagInstance, candidate: Candidate) -> None:
    batch = embed([segment.text for segment in candidate.segments], instance.embedding_model)
    candidate.vectors = {
        segment.id: vector for segment, vector in zip(candidate.segments, batch.vectors)
    }
    candidate.embedding_provider = batch.provider
    candidate.embedding_dimension = batch.dimension
    candidate.embedding_warning = batch.warning
    document = instance.documents.get(candidate.document_id)
    if document:
        document.model_metadata = {
            "version": MODEL_PROVENANCE_VERSION,
            "embedding_model": instance.embedding_model,
            "embedding_provider": batch.provider,
            "embedding_dimension": batch.dimension,
            "embedding_warning": batch.warning,
            "retrieval_configs": sorted(
                {CANDIDATES[candidate_id].retrieval_config for candidate_id in document.candidate_ids if candidate_id in CANDIDATES}
            ),
            "indexed_at": now(),
        }


def register_artifact(
    instance: RagInstance,
    *,
    type: str,
    title: str,
    context_document_ids: list[str],
    metadata: dict,
    payload: dict | None = None,
    artifact_status: ArtifactStatus = ArtifactStatus.READY,
) -> Artifact:
    created_at = datetime.now(UTC)
    artifact = Artifact(
        id=new_id(),
        instance_id=instance.id,
        type=type,
        title=title,
        status=artifact_status,
        context_document_ids=context_document_ids,
        metadata=metadata,
        payload=payload or {},
        created_at=created_at,
        updated_at=created_at,
    )
    ARTIFACTS[artifact.id] = artifact
    instance.artifact_ids.append(artifact.id)
    return artifact


def artifact_payload(artifact: Artifact, include_payload: bool = False) -> dict:
    payload = {
        "id": artifact.id,
        "type": artifact.type,
        "title": artifact.title,
        "status": artifact.status,
        "context_document_ids": artifact.context_document_ids,
        "context_status": artifact.metadata.get("context_status", "AVAILABLE"),
        "metadata": artifact.metadata,
        "available_actions": ["open", "delete"],
        "created_at": artifact.created_at.isoformat(),
        "updated_at": artifact.updated_at.isoformat(),
    }
    if include_payload:
        payload["payload"] = artifact.payload
    return payload


def latest_job_for(instance_id: str) -> ProcessingJob | None:
    jobs = [job for job in JOBS.values() if job.instance_id == instance_id]
    return max(jobs, key=lambda job: job.created_at) if jobs else None


def latest_round_for(instance_id: str) -> ComparisonRound | None:
    rounds = [round_ for round_ in ROUNDS.values() if round_.instance_id == instance_id]
    return max(rounds, key=lambda round_: round_.created_at) if rounds else None


def feedback_age_weight(created_at: str) -> tuple[float, str]:
    """Keep recency explicit instead of treating years-old feedback as current."""
    try:
        age_days = max(0, (datetime.now(UTC) - datetime.fromisoformat(created_at)).days)
    except (TypeError, ValueError):
        return 0.25, "UNKNOWN_TIMESTAMP"
    if age_days <= 14:
        return 1.0, "0_14_DAYS"
    if age_days <= 60:
        return 0.5, "15_60_DAYS"
    return 0.25, "61_PLUS_DAYS"


def answer_integrity_observations(instance: RagInstance) -> dict:
    """Report stored answer facts, never inferred model-quality scores."""
    answer_artifacts = [
        artifact
        for artifact_id in instance.artifact_ids
        for artifact in [ARTIFACTS.get(artifact_id)]
        if artifact and artifact.type == "ANSWER"
    ]
    counts = {
        "answer_count": len(answer_artifacts),
        "answer_artifact_ids": [artifact.id for artifact in answer_artifacts],
        "ungrounded_count": 0,
        "fallback_count": 0,
        "missing_citation_count": 0,
    }
    affected_document_ids: set[str] = set()
    for artifact in answer_artifacts:
        generation = artifact.metadata.get("generation", {})
        grounded = bool(artifact.metadata.get("grounded"))
        citations = artifact.payload.get("citations", [])
        problematic = False
        if not grounded:
            counts["ungrounded_count"] += 1
            problematic = True
        if generation.get("fallback"):
            counts["fallback_count"] += 1
            problematic = True
        if grounded and not citations:
            counts["missing_citation_count"] += 1
            problematic = True
        if problematic:
            affected_document_ids.update(document_id for document_id in artifact.context_document_ids if document_id in instance.documents)
    counts["integrity_event_count"] = counts["ungrounded_count"] + counts["fallback_count"] + counts["missing_citation_count"]
    counts["affected_document_ids"] = sorted(affected_document_ids)
    counts["interpretation"] = "저장된 grounded/fallback/citation 사실이며 모델 품질 점수가 아닙니다."
    return counts


def benchmark_provider_snapshot() -> dict:
    if not BENCHMARK_RUNS:
        return {
            "available": False,
            "status": "NOT_RUN",
            "used_for_recommendation_score": False,
            "reason": "실측 benchmark가 없어 모델 품질을 추천 점수에 사용하지 않습니다.",
            "run": None,
            "results": [],
        }
    latest = BENCHMARK_RUNS[-1]
    results = [
        {
            "model_id": result.get("model_id"),
            "status": result.get("status"),
            "provider": result.get("provider"),
            "dimension": result.get("dimension"),
        }
        for result in latest.get("results", [])
    ]
    release_evidence = bool(results) and all(
        result["status"] == "COMPLETED" and "fallback" not in str(result["provider"]).lower()
        for result in results
    )
    return {
        "available": True,
        "status": "REAL_PROVIDER_EVIDENCE" if release_evidence else "NOT_RELEASE_EVIDENCE",
        "used_for_recommendation_score": False,
        "reason": (
            "실제 provider benchmark 상태는 재튜닝 전 runtime 검토 정보로만 사용하며, 모델 품질 점수로 합산하지 않습니다."
            if release_evidence
            else "fallback·실패·부분 benchmark는 모델 품질 근거가 아니므로 추천 점수에 사용하지 않습니다."
        ),
        "run": {"id": latest.get("run", {}).get("id"), "created_at": latest.get("run", {}).get("created_at"), "corpus_label": latest.get("run", {}).get("corpus_label")},
        "results": results,
    }


def feedback_signal(instance: RagInstance) -> dict:
    """Persistable, explainable retuning recommendation with no synthetic quality claim."""
    items = [item for item in FEEDBACK if item["instance_id"] == instance.id]
    negative = [item for item in items if item["rating"] < 0]
    positive = [item for item in items if item["rating"] > 0]
    recency_buckets = {"0_14_DAYS": 0, "15_60_DAYS": 0, "61_PLUS_DAYS": 0, "UNKNOWN_TIMESTAMP": 0}
    negative_weight = 0.0
    target_document_ids: set[str] = set()
    for item in negative:
        weight, bucket = feedback_age_weight(item.get("created_at", ""))
        negative_weight += weight
        recency_buckets[bucket] += 1
        target_document_ids.update(document_id for document_id in item.get("document_ids", []) if document_id in instance.documents)
    observations = answer_integrity_observations(instance)
    target_document_ids.update(observations["affected_document_ids"])
    if not target_document_ids:
        target_document_ids.update(document.id for document in instance.documents.values() if document.finalized_candidate_id)
    feedback_trigger = negative_weight >= RETUNING_NEGATIVE_WEIGHT_THRESHOLD
    integrity_trigger = observations["integrity_event_count"] >= RETUNING_INTEGRITY_EVENT_THRESHOLD
    combined_trigger = bool(negative) and observations["integrity_event_count"] >= 1
    reasons = []
    if feedback_trigger:
        reasons.append("RECENT_NEGATIVE_FEEDBACK_THRESHOLD")
    if integrity_trigger:
        reasons.append("ANSWER_INTEGRITY_EVENTS_THRESHOLD")
    if combined_trigger and not (feedback_trigger or integrity_trigger):
        reasons.append("FEEDBACK_AND_ANSWER_INTEGRITY")
    benchmark = benchmark_provider_snapshot()
    if benchmark["status"] != "REAL_PROVIDER_EVIDENCE":
        reasons.append("BENCHMARK_NOT_QUALITY_EVIDENCE")
    recommended = feedback_trigger or integrity_trigger or combined_trigger
    return {
        "version": RETUNING_SIGNAL_VERSION,
        "recommended": recommended,
        "negative_count": len(negative),
        "positive_count": len(positive),
        # Retained as a numeric field for first-slice clients; it now means
        # recency-weighted negative feedback, not a fixed count of three.
        "threshold": RETUNING_NEGATIVE_WEIGHT_THRESHOLD,
        "threshold_details": {
            "negative_feedback_weight": RETUNING_NEGATIVE_WEIGHT_THRESHOLD,
            "answer_integrity_events": RETUNING_INTEGRITY_EVENT_THRESHOLD,
            "combined_rule": "at least one negative feedback plus at least one stored integrity event",
        },
        "inputs": {
            "feedback": {
                "total": len(items),
                "negative_count": len(negative),
                "positive_count": len(positive),
                "recency_buckets": recency_buckets,
                "negative_recency_weight": round(negative_weight, 3),
            },
            "answer_integrity": observations,
            "benchmark_provider": benchmark,
        },
        "recommendation_reasons": reasons,
        "eligible_document_ids": sorted(target_document_ids),
        "message": (
            "저장된 피드백과 답변 무결성 신호를 바탕으로 재튜닝을 권장합니다."
            if recommended
            else "현재 저장된 피드백·답변 무결성 신호만으로는 재튜닝을 권장하지 않습니다."
        ),
        "action": "START_RETUNE" if recommended else None,
        "runtime_review": "VERIFY_BENCHMARK_AND_PROVIDER" if benchmark["status"] != "REAL_PROVIDER_EVIDENCE" else None,
    }


def retuning_baseline_snapshot(instance: RagInstance, document_ids: list[str]) -> dict:
    """Freeze the prior chosen pipeline and observed evidence before destructive retuning."""
    pipelines = []
    for document_id in document_ids:
        document = instance.documents[document_id]
        candidate = CANDIDATES[document.finalized_candidate_id]
        pipelines.append(
            {
                "document_id": document.id,
                "filename": document.filename,
                "pipeline": candidate_payload(candidate),
                "comparison": comparison_plan_payload(document),
                "full_reindex": full_reindex_payload(document),
            }
        )
    return {
        "version": RETUNING_SIGNAL_VERSION,
        "captured_at": now(),
        "document_ids": document_ids,
        "selected_pipelines": pipelines,
        "recommendation": feedback_signal(instance),
    }


def tokenize(value: str) -> set[str]:
    text = re.sub(r"[^0-9A-Za-z가-힣]+", " ", value.lower())
    words = {word for word in text.split() if len(word) > 1}
    # Korean particles make word-only matching brittle; add compact character n-grams.
    compact = re.sub(r"\s+", "", text)
    grams = {compact[i : i + 2] for i in range(max(0, len(compact) - 1))}
    return words | grams


def score(question: str, segment: Segment, retrieval: str) -> float:
    q_tokens, s_tokens = tokenize(question), tokenize(segment.text)
    overlap = len(q_tokens & s_tokens)
    if not q_tokens:
        return 0.0
    base = overlap / len(q_tokens)
    if retrieval == "hybrid_rerank":
        return min(1.0, base * 1.15)
    if retrieval == "bm25":
        return min(1.0, base * 1.05)
    return base


def evidence_for(
    segments: list[Segment],
    question: str,
    retrieval: str,
    *,
    vectors: dict[str, list[float]] | None = None,
    embedding_model: str = "BGE-M3",
) -> tuple[Segment | None, float, dict]:
    if vectors and all(segment.id in vectors for segment in segments):
        scores, query_batch, ranking_metadata = rank_segments(
            query=question,
            texts=[segment.text for segment in segments],
            vectors=[vectors[segment.id] for segment in segments],
            retrieval_config=retrieval,
            model_name=embedding_model,
        )
        if not scores:
            return None, 0.0, {"provider": query_batch.provider, "warning": query_batch.warning, **ranking_metadata}
        index = max(range(len(scores)), key=scores.__getitem__)
        return segments[index], scores[index], {
            "provider": query_batch.provider,
            "dimension": query_batch.dimension,
            "warning": query_batch.warning,
            **ranking_metadata,
        }
    best: tuple[Segment | None, float] = (None, 0.0)
    for segment in segments:
        segment_score = score(question, segment, retrieval)
        if segment_score > best[1]:
            best = (segment, segment_score)
    return *best, {"provider": "legacy-lexical"}


def citation_payload(document: Document, segment: Segment, number: int) -> dict:
    return {
        "id": segment.id,
        "number": number,
        "segment_id": segment.id,
        "document_id": document.id,
        "filename": document.filename,
        "title": f"{document.filename} · 조각 {segment.ordinal}",
        "excerpt": segment.text,
        "ordinal": segment.ordinal,
        "location": {
            "kind": "text",
            "ordinal": segment.ordinal,
            "start_offset": segment.start_offset,
            "end_offset": segment.end_offset,
        },
        "navigate_url": f"{API_PREFIX}/documents/{document.id}/segments/{segment.id}",
    }


class GroundingValidationError(ValueError):
    """A generator response did not cite every sentence with supplied context."""


def extractive_sentence(segment: Segment) -> str:
    sentence = segment.text.split(". ")[0].strip()
    if not sentence.endswith((".", "다.", "요.")):
        sentence += "."
    return sentence


def bounded_positive_env(name: str, default: int) -> int:
    """Read a bounded retrieval knob without letting invalid env values break search."""
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def multi_document_context_limit() -> int:
    return bounded_positive_env("RAG_MULTI_DOCUMENT_CONTEXT_LIMIT", DEFAULT_MULTI_DOCUMENT_CONTEXT_LIMIT)


def multi_document_rerank_top_k() -> int:
    return bounded_positive_env("RAG_MULTI_DOCUMENT_RERANK_TOP_K", DEFAULT_MULTI_DOCUMENT_RERANK_TOP_K)


def render_validated_generation(
    generated: GenerationResult,
    citations_by_segment_id: dict[str, dict],
) -> tuple[str, list[dict], list[list[str]]]:
    """Render model text only after every sentence has valid source IDs."""
    if not generated.sentences:
        raise GroundingValidationError("generated response requires at least one cited sentence")
    supplied_ids = set(citations_by_segment_id)
    used_ids: list[str] = []
    sentences: list[str] = []
    sentence_citation_ids: list[list[str]] = []
    for generated_sentence in generated.sentences:
        text = generated_sentence.text.strip()
        citation_ids = generated_sentence.citation_ids
        if not text or not citation_ids:
            raise GroundingValidationError("every generated sentence requires at least one citation")
        if any(citation_id not in supplied_ids for citation_id in citation_ids):
            raise GroundingValidationError("generated citation does not reference supplied segment IDs")
        unique_sentence_ids = list(dict.fromkeys(citation_ids))
        for citation_id in unique_sentence_ids:
            if citation_id not in used_ids:
                used_ids.append(citation_id)
        sentence_citation_ids.append(unique_sentence_ids)
        sentences.append(text)
    citations = [{**citations_by_segment_id[citation_id], "number": index} for index, citation_id in enumerate(used_ids, start=1)]
    citation_numbers = {citation["segment_id"]: citation["number"] for citation in citations}
    answer = " ".join(
        f"{sentence} {' '.join(f'[{citation_numbers[citation_id]}]' for citation_id in citation_ids)}"
        for sentence, citation_ids in zip(sentences, sentence_citation_ids)
    )
    return answer, citations, sentence_citation_ids


def grounded_generation_for(question: str, document: Document, segment: Segment) -> tuple[str, list[dict], dict]:
    return grounded_generation_for_contexts(question, [(document, segment)])


def grounded_generation_for_contexts(
    question: str,
    contexts: list[tuple[Document, Segment]],
) -> tuple[str, list[dict], dict]:
    """Generate only from a bounded set of retrieved cross-document contexts."""
    citations_by_segment_id = {
        segment.id: citation_payload(document, segment, index)
        for index, (document, segment) in enumerate(contexts, start=1)
    }
    supplied_segment_ids = list(citations_by_segment_id)
    try:
        generated = generate_grounded(
            question=question,
            contexts=[{"segment_id": segment.id, "text": segment.text} for _, segment in contexts],
        )
        answer, citations, sentence_citation_ids = render_validated_generation(generated, citations_by_segment_id)
        return answer, citations, {
            "mode": "MODEL",
            "provider": generated.provider,
            "model": generated.model,
            "latency_ms": generated.latency_ms,
            "fallback": False,
            "fallback_reason": None,
            "grounding_valid": True,
            "supplied_segment_ids": supplied_segment_ids,
            "sentence_citation_ids": sentence_citation_ids,
        }
    except GroundingValidationError as error:
        fallback_reason = "INVALID_GROUNDING"
        failure = str(error)
    except GenerationEndpointError as error:
        fallback_reason = "GENERATOR_UNAVAILABLE"
        failure = str(error)
    # The fallback stays within the same bounded evidence set and still exposes
    # source IDs per sentence, so a bad model response cannot leak ungrounded text.
    fallback_contexts = contexts[: min(2, len(contexts))]
    fallback_citations = [
        {**citations_by_segment_id[segment.id], "number": index}
        for index, (_, segment) in enumerate(fallback_contexts, start=1)
    ]
    fallback_answer = " ".join(
        f"{extractive_sentence(segment)} [{index}]"
        for index, (_, segment) in enumerate(fallback_contexts, start=1)
    )
    return fallback_answer, fallback_citations, {
        "mode": "EXTRACTIVE_FALLBACK",
        "provider": "extractive-fallback",
        "model": None,
        "latency_ms": 0,
        "fallback": True,
        "fallback_reason": fallback_reason,
        "failure": failure,
        "grounding_valid": True,
        "supplied_segment_ids": supplied_segment_ids,
        "sentence_citation_ids": [[segment.id] for _, segment in fallback_contexts],
    }


def answer_for(
    document: Document,
    question: str,
    retrieval: str,
    sensitivity: Sensitivity = Sensitivity.BALANCED,
    segments: list[Segment] | None = None,
    vectors: dict[str, list[float]] | None = None,
    embedding_model: str = "BGE-M3",
) -> dict:
    segment, relevance, retrieval_metadata = evidence_for(
        segments if segments is not None else document.segments,
        question,
        retrieval,
        vectors=vectors,
        embedding_model=embedding_model,
    )
    thresholds = {Sensitivity.FLEXIBLE: 0.05, Sensitivity.BALANCED: 0.12, Sensitivity.STRICT: 0.24}
    if not segment or relevance < thresholds[sensitivity]:
        return {
            "answer": "관련 문서를 찾지 못했습니다. 검색 범위나 질문을 조금 더 구체적으로 바꿔보세요.",
            "citations": [],
            "relevance": round(relevance, 3),
            "grounded": False,
            "retrieval_metadata": retrieval_metadata,
            "generation": {
                "mode": "NOT_ATTEMPTED",
                "provider": None,
                "fallback": False,
                "fallback_reason": "NO_RETRIEVED_EVIDENCE",
                "grounding_valid": True,
                "supplied_segment_ids": [],
                "sentence_citation_ids": [],
            },
        }
    answer, citations, generation = grounded_generation_for(question, document, segment)
    return {
        "answer": answer,
        "citations": citations,
        "relevance": round(relevance, 3),
        "grounded": True,
        "retrieval_metadata": retrieval_metadata,
        "generation": generation,
    }


def grouped_citations(citations: list[dict], documents: list[Document]) -> list[dict]:
    """Keep the flat citation contract while making cross-document provenance explicit."""
    document_order = {document.id: index for index, document in enumerate(documents)}
    groups: dict[str, dict] = {}
    for citation in citations:
        group = groups.setdefault(
            citation["document_id"],
            {
                "document_id": citation["document_id"],
                "filename": citation["filename"],
                "citations": [],
            },
        )
        group["citations"].append(citation)
    return sorted(groups.values(), key=lambda group: document_order.get(group["document_id"], len(document_order)))


def retrieve_document_candidates(
    document: Document,
    candidate: Candidate,
    question: str,
    embedding_model: str,
    retrieval_override: str | None,
) -> tuple[list[dict], dict]:
    """Retrieve within one finalized document before any cross-document merge."""
    retrieval_config = retrieval_override or candidate.retrieval_config
    segments = candidate.segments
    ranking_metadata: dict
    if candidate.vectors and all(segment.id in candidate.vectors for segment in segments):
        # Existing rank() reranks the full list. Multi-document search first
        # narrows by hybrid retrieval and reranks only this document's top-k.
        base_config = "hybrid" if retrieval_config == "hybrid_rerank" else retrieval_config
        scores, query_batch, ranking_metadata = rank_segments(
            query=question,
            texts=[segment.text for segment in segments],
            vectors=[candidate.vectors[segment.id] for segment in segments],
            retrieval_config=base_config,
            model_name=embedding_model,
        )
        ranking_metadata = {
            "provider": query_batch.provider,
            "dimension": query_batch.dimension,
            "warning": query_batch.warning,
            **ranking_metadata,
        }
    else:
        scores = [score(question, segment, retrieval_config) for segment in segments]
        ranking_metadata = {"provider": "legacy-lexical", "dimension": None, "warning": None}

    rerank_metadata = {
        "configured": retrieval_config == "hybrid_rerank",
        "applied": False,
        "top_k": 0,
        "provider": None,
        "warning": None,
    }
    if retrieval_config == "hybrid_rerank" and scores:
        top_k = min(multi_document_rerank_top_k(), len(scores))
        top_indices = sorted(range(len(scores)), key=scores.__getitem__, reverse=True)[:top_k]
        rerank_scores, provider, warning = rerank_segments(question, [segments[index].text for index in top_indices])
        for index, rerank_score in zip(top_indices, rerank_scores):
            scores[index] = 0.7 * scores[index] + 0.3 * rerank_score
        rerank_metadata = {
            "configured": True,
            "applied": True,
            "top_k": top_k,
            "provider": provider,
            "warning": warning,
        }

    maximum = max(scores, default=0.0)
    ordered = sorted(range(len(scores)), key=scores.__getitem__, reverse=True)
    entries = [
        {
            "document": document,
            "candidate": candidate,
            "segment": segments[index],
            "raw_score": scores[index],
            "normalized_score": scores[index] / maximum if maximum else 0.0,
            "document_rank": rank + 1,
        }
        for rank, index in enumerate(ordered)
    ]
    metadata = {
        "document_id": document.id,
        "filename": document.filename,
        "candidate_id": candidate.id,
        "retrieval_config": retrieval_config,
        "retrieval_config_source": "request_override" if retrieval_override else "document_finalized",
        "candidate_chunk_count": len(segments),
        "retrieved_count": len(entries),
        "score_normalization": {"method": "per_document_max", "maximum_raw_score": round(maximum, 6)},
        "rerank": rerank_metadata,
        "ranking": ranking_metadata,
        "top_candidates": [
            {
                "segment_id": entry["segment"].id,
                "raw_score": round(entry["raw_score"], 6),
                "normalized_score": round(entry["normalized_score"], 6),
                "document_rank": entry["document_rank"],
            }
            for entry in entries[: min(5, len(entries))]
        ],
    }
    return entries, metadata


def answer_for_documents(
    documents: list[Document],
    question: str,
    sensitivity: Sensitivity,
    embedding_model: str,
    retrieval_override: str | None,
) -> dict:
    """Merge independently tuned sources into one bounded grounded answer."""
    per_document_entries: list[dict] = []
    document_metadata: list[dict] = []
    for document in documents:
        candidate = CANDIDATES[document.finalized_candidate_id]
        entries, metadata = retrieve_document_candidates(
            document, candidate, question, embedding_model, retrieval_override
        )
        per_document_entries.extend(entries)
        document_metadata.append(metadata)

    document_order = {document.id: index for index, document in enumerate(documents)}
    merged = sorted(
        per_document_entries,
        key=lambda entry: (
            -entry["normalized_score"],
            document_order[entry["document"].id],
            entry["document_rank"],
        ),
    )
    context_limit = multi_document_context_limit()
    selected = [entry for entry in merged if entry["normalized_score"] > 0][:context_limit]
    thresholds = {Sensitivity.FLEXIBLE: 0.05, Sensitivity.BALANCED: 0.12, Sensitivity.STRICT: 0.24}
    relevance = selected[0]["normalized_score"] if selected else 0.0
    retrieval_metadata = {
        "mode": "MULTI_DOCUMENT",
        "merge": {
            "strategy": "per_document_max_normalized_global_merge",
            "context_limit": context_limit,
            "selected_context_count": len(selected),
            "threshold": thresholds[sensitivity],
        },
        "documents": document_metadata,
        "global_candidates": [
            {
                "document_id": entry["document"].id,
                "filename": entry["document"].filename,
                "segment_id": entry["segment"].id,
                "raw_score": round(entry["raw_score"], 6),
                "normalized_score": round(entry["normalized_score"], 6),
                "document_rank": entry["document_rank"],
            }
            for entry in merged[: min(20, len(merged))]
        ],
    }
    if not selected or relevance < thresholds[sensitivity]:
        return {
            "answer": "관련 문서를 찾지 못했습니다. 검색 범위나 질문을 조금 더 구체적으로 바꿔보세요.",
            "citations": [],
            "grouped_citations": [],
            "relevance": round(relevance, 3),
            "grounded": False,
            "retrieval_metadata": retrieval_metadata,
            "generation": {
                "mode": "NOT_ATTEMPTED",
                "provider": None,
                "fallback": False,
                "fallback_reason": "NO_RETRIEVED_EVIDENCE",
                "grounding_valid": True,
                "supplied_segment_ids": [],
                "sentence_citation_ids": [],
            },
        }
    answer, citations, generation = grounded_generation_for_contexts(
        question,
        [(entry["document"], entry["segment"]) for entry in selected],
    )
    return {
        "answer": answer,
        "citations": citations,
        "grouped_citations": grouped_citations(citations, documents),
        "relevance": round(relevance, 3),
        "grounded": True,
        "retrieval_metadata": retrieval_metadata,
        "generation": generation,
    }


def candidate_payload(candidate: Candidate) -> dict:
    return {
        "id": candidate.id,
        "document_id": candidate.document_id,
        "chunking_strategy": candidate.chunking_strategy,
        "retrieval_config": candidate.retrieval_config,
        "friendly_name": candidate.friendly_name,
        "technical_description": candidate.technical_description,
        "chunking_parameters": candidate.chunking_parameters,
        "selection_reason": candidate.selection_reason,
        "is_temporary": candidate.is_temporary,
        "selection_count": candidate.selection_count,
        "finalized": candidate.finalized,
        "chunk_count": len(candidate.segments),
        "comparison": {
            "scope": candidate.comparison_scope,
            "estimated_chunk_count": candidate.estimated_chunk_count,
            "selected_chunk_count": candidate.selected_chunk_count,
        },
        "preparation": {
            "state": candidate.preparation_state,
            "ready": candidate.preparation_state == CandidateState.READY,
            "error": candidate.preparation_error,
            "prepared_at": encode_time(candidate.prepared_at),
        },
        "index": {
            "vector_count": len(candidate.vectors),
            "embedding_provider": candidate.embedding_provider,
            "embedding_dimension": candidate.embedding_dimension,
            "warning": candidate.embedding_warning,
        },
        "exploration": {
            "round_id": candidate.exploration_round_id,
            "parent_candidate_id": candidate.parent_candidate_id,
            "archived": candidate.archived,
        },
    }


def instance_payload(instance: RagInstance, include_documents: bool = False) -> dict:
    latest_job = latest_job_for(instance.id)
    payload = {
        "id": instance.id,
        "name": instance.name,
        "status": instance.status,
        "embedding_model": instance.embedding_model,
        "graphrag_enabled": instance.graphrag_enabled,
        "document_count": len(instance.documents),
        "artifact_count": len(instance.artifact_ids),
        "latest_job": job_payload(latest_job) if latest_job else None,
        "retuning_signal": feedback_signal(instance),
        "created_at": instance.created_at.isoformat(),
    }
    if include_documents:
        payload["documents"] = [document_payload(document) for document in instance.documents.values()]
        latest_round = latest_round_for(instance.id)
        payload["latest_round"] = round_detail_payload(instance, latest_round) if latest_round else None
    return payload


def document_payload(document: Document) -> dict:
    return {
        "id": document.id,
        "filename": document.filename,
        "content_type": document.content_type,
        "source": document.source_metadata,
        "provenance": {
            "source_version": SOURCE_PROVENANCE_VERSION,
            "parser": document.parser_metadata,
            "chunking": document.chunking_metadata,
            "model": document.model_metadata,
        },
        "profile": document.profile,
        "chunking_analysis": document.chunking_analysis,
        "parse_status": document.parse_status,
        "parser": document.parser,
        "used_ocr": document.used_ocr,
        "processing_job_id": document.processing_job_id,
        "pipeline_mode": document.pipeline_mode,
        "comparison": comparison_plan_payload(document),
        "full_reindex": full_reindex_payload(document),
        "segment_count": len(document.segments),
        "finalized_candidate_id": document.finalized_candidate_id,
        "created_at": document.created_at.isoformat(),
        "candidates": [candidate_payload(CANDIDATES[candidate_id]) for candidate_id in document.candidate_ids],
    }


def full_reindex_payload(document: Document) -> dict:
    """One explicit search-eligibility contract for sampled finalized sources."""
    state = document.full_reindex_state
    ready = state in {None, JobState.SUCCEEDED}
    failed = state in {JobState.FAILED, JobState.CANCELLED}
    return {
        "required": document.comparison_scope == ComparisonScope.SAMPLE,
        "job_id": document.full_reindex_job_id,
        "state": state,
        "ready": ready,
        "search_eligible": ready,
        "search_policy": "BLOCK_UNTIL_FULL_INDEX_SUCCEEDED",
        "next_action": "RETRY_FULL_REINDEX" if failed else ("WAIT_FOR_FULL_REINDEX" if not ready else None),
    }


def comparison_plan_payload(document: Document) -> dict:
    return {
        "scope": document.comparison_scope,
        "chunk_threshold": document.comparison_chunk_threshold,
        "estimated_chunk_count": document.estimated_chunk_count,
        "selected_chunk_count": document.selected_chunk_count,
        "candidate_chunk_counts": document.candidate_chunk_counts,
        "full_source_retained": True,
    }


app = FastAPI(title="RAG Portal MVP API", version="0.1.0", openapi_url=f"{API_PREFIX}/openapi.json", docs_url="/docs")
app.add_middleware(
    CORSMiddleware,
    # Vite picks the next free port when a nearby project is already running.
    # This applies only to loopback origins, never to arbitrary remote hosts.
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "rag-portal-api", "time": now()}


@app.get(f"{API_PREFIX}/model-runtime")
def get_model_runtime() -> dict:
    """Expose configured model services instead of hiding deployment prerequisites."""
    services = runtime_catalog()
    return {
        "services": services,
        "items": services,
        "catalog_ready": all(service["ready"] for service in services),
        "production_policy": "인스턴스별 execution plan의 모든 필수 모델 서비스가 READY여야 문서 처리와 검색을 시작합니다.",
    }


@app.get(f"{API_PREFIX}/large-document-policy")
def get_large_document_policy() -> dict:
    return {
        "comparison_chunk_threshold": comparison_chunk_threshold(),
        "default_comparison_chunk_threshold": DEFAULT_COMPARISON_CHUNK_THRESHOLD,
        "scope_rule": "각 청킹 전략의 예상 청크 수가 임계값을 초과하면 SAMPLE 비교를 사용하고, 확정 뒤 FULL_REINDEX job을 생성합니다.",
        "sample_selection": "문서 첫·중간·끝 범위를 고르게 포함하는 결정론적 간격 샘플",
    }


BENCHMARK_CORPUS = [
    "국내 출장 숙박비는 1박 10만원을 한도로 합니다.",
    "해외 출장 식비는 국가 등급에 따라 하루 80달러에서 150달러입니다.",
    "연차 휴가는 사전에 승인받아야 합니다.",
]
BENCHMARK_QUERIES = [
    ("국내 출장 숙박비 한도는?", 0),
    ("해외 출장 식비는 얼마인가요?", 1),
    ("연차 휴가 신청 절차는?", 2),
]


def run_embedding_benchmark() -> dict:
    """Run a small versioned golden set through the same embedding contract as retrieval."""
    results = []
    for model_id in ("BGE-M3", "Qwen3-Embedding-0.6B", "EmbeddingGemma-300M"):
        try:
            corpus_batch = embed(BENCHMARK_CORPUS, model_id)
            ranks = []
            latencies = [corpus_batch.latency_ms]
            for question, expected_index in BENCHMARK_QUERIES:
                scores, query_batch, _ = rank_segments(
                    query=question,
                    texts=BENCHMARK_CORPUS,
                    vectors=corpus_batch.vectors,
                    retrieval_config="dense",
                    model_name=model_id,
                )
                ordered = sorted(range(len(scores)), key=scores.__getitem__, reverse=True)
                ranks.append(ordered.index(expected_index) + 1)
                latencies.append(query_batch.latency_ms)
            provider = corpus_batch.provider
            results.append(
                {
                    "model_id": model_id,
                    "recall_at_1": round(sum(rank == 1 for rank in ranks) / len(ranks), 3),
                    "recall_at_5": round(sum(rank <= 5 for rank in ranks) / len(ranks), 3),
                    "mrr": round(sum(1 / rank for rank in ranks) / len(ranks), 3),
                    "average_latency_ms": round(sum(latencies) / len(latencies)),
                    "dimension": corpus_batch.dimension,
                    "provider": provider,
                    "status": "FALLBACK" if "fallback" in provider else "COMPLETED",
                }
            )
        except Exception as error:
            results.append({"model_id": model_id, "recall_at_1": None, "recall_at_5": None, "mrr": None, "average_latency_ms": None, "dimension": None, "provider": "unavailable", "status": "FAILED", "error": str(error)})
    run = {"id": new_id(), "corpus_label": "Sprint 07 golden corpus v1", "query_count": len(BENCHMARK_QUERIES), "created_at": now()}
    benchmark = {"run": run, "results": results}
    BENCHMARK_RUNS.append(benchmark)
    persist_state()
    return benchmark


@app.post(f"{API_PREFIX}/embedding-benchmarks/run")
def create_embedding_benchmark() -> dict:
    return run_embedding_benchmark()


@app.get(f"{API_PREFIX}/embedding-benchmarks/latest")
def get_latest_embedding_benchmark() -> dict:
    if not BENCHMARK_RUNS:
        raise HTTPException(404, detail={"code": "BENCHMARK_NOT_RUN", "message": "아직 우리 문서 실측 결과를 실행하지 않았습니다."})
    return BENCHMARK_RUNS[-1]


@app.get(f"{API_PREFIX}/rag-instances")
def list_instances() -> dict:
    return {"items": [instance_payload(instance) for instance in sorted(INSTANCES.values(), key=lambda item: item.created_at, reverse=True)], "total": len(INSTANCES)}


@app.post(f"{API_PREFIX}/rag-instances/embedding-recommendations")
def get_embedding_recommendations(questionnaire: Questionnaire) -> dict:
    items = embedding_recommendations(questionnaire)
    return {"items": items, "recommended_model": items[0]["id"]}


@app.post(f"{API_PREFIX}/rag-instances", status_code=status.HTTP_201_CREATED)
def create_instance(body: InstanceCreate) -> dict:
    recommendations = embedding_recommendations(body.questionnaire)
    instance = RagInstance(
        id=new_id(),
        name=body.name,
        status=InstanceStatus.SETTING_UP,
        embedding_model=recommend_embedding(body.questionnaire),
        graphrag_enabled=body.questionnaire.multi_hop_questions,
    )
    INSTANCES[instance.id] = instance
    persist_state()
    return {
        **instance_payload(instance),
        "recommendation": {
            "embedding_model": instance.embedding_model,
            "reason": "추천 후보 중 선택한 임베딩 모델을 이 지식 공간 전체에 고정했습니다.",
            "candidates": recommendations,
        },
    }


@app.get(f"{API_PREFIX}/rag-instances/{{instance_id}}")
def get_instance_detail(instance_id: str) -> dict:
    return instance_payload(get_instance(instance_id), include_documents=True)


@app.get(f"{API_PREFIX}/rag-instances/{{instance_id}}/execution-plan")
def get_instance_execution_plan(instance_id: str) -> dict:
    """Return the model-dependent techniques required by this RAG instance."""
    instance = get_instance(instance_id)
    candidates = [CANDIDATES[candidate_id] for candidate_id in instance.candidate_ids if candidate_id in CANDIDATES]
    retrieval_configs = [candidate.retrieval_config for candidate in candidates]
    # A new instance will produce the full comparison matrix on its first upload.
    # Include that planned reranker requirement before the candidates exist.
    if not retrieval_configs:
        retrieval_configs = ["bm25", "dense", "hybrid_rerank"]
    plan = execution_plan(
        embedding_model=instance.embedding_model,
        document_profiles=[document.profile for document in instance.documents.values()],
        retrieval_configs=retrieval_configs,
    )
    return {
        "instance_id": instance.id,
        "instance_name": instance.name,
        "document_count": len(instance.documents),
        "candidate_count": len(candidates),
        **plan,
    }


def resolved_pipeline_mode(body: DocumentsCreate) -> PipelineMode:
    if body.reuse_finalized_pipeline is True:
        if body.pipeline_mode == PipelineMode.RETUNE:
            return PipelineMode.REUSE
    return body.pipeline_mode


def job_stages(mode: PipelineMode) -> list[dict]:
    return [
        {"key": "PARSING", "label": "문서 구조를 읽는 중", "state": "QUEUED", "completed_at": None},
        {"key": "CANDIDATES", "label": "비교 후보를 준비하는 중" if mode == PipelineMode.RETUNE else "확정된 설정을 적용하는 중", "state": "QUEUED", "completed_at": None},
        {"key": "INDEXING", "label": "검색용 결과물을 준비하는 중", "state": "QUEUED", "completed_at": None},
    ]


def full_reindex_stages() -> list[dict]:
    return [
        {"key": "FULL_CHUNKING", "label": "확정된 설정으로 전체 문서를 다시 나누는 중", "state": "QUEUED", "completed_at": None},
        {"key": "FULL_INDEXING", "label": "전체 문서 검색 인덱스를 만드는 중", "state": "QUEUED", "completed_at": None},
    ]


def job_max_attempts() -> int:
    try:
        return max(1, int(os.getenv("RAG_JOB_MAX_ATTEMPTS", "3")))
    except ValueError:
        return 3


def job_retry_backoff_seconds() -> int:
    try:
        return max(0, int(os.getenv("RAG_JOB_RETRY_BACKOFF_SECONDS", "0")))
    except ValueError:
        return 0


def ensure_job_operational_fields(job: ProcessingJob) -> None:
    if not job.idempotency_key:
        scope = ",".join(sorted(job.document_ids))
        job.idempotency_key = f"{job.kind}:{job.instance_id}:{scope}:{job.artifact_id or job.id}"
    job.max_attempts = max(1, job.max_attempts or job_max_attempts())
    job.retry_backoff_seconds = max(0, job.retry_backoff_seconds or job_retry_backoff_seconds())


def worker_identity() -> str:
    return os.getenv("RAG_WORKER_ID", f"{backend_name()}-worker")


def claim_job_execution(job: ProcessingJob) -> bool:
    """Durable in-process lease; duplicate adapter deliveries become no-ops."""
    ensure_job_operational_fields(job)
    if job.execution_status == "RUNNING":
        return False
    if job.state in {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED, JobState.DEAD_LETTER}:
        return False
    job.execution_status = "RUNNING"
    job.execution_count += 1
    job.worker_id = worker_identity()
    job.last_heartbeat_at = datetime.now(UTC)
    return True


def complete_job_execution(job: ProcessingJob) -> None:
    job.execution_status = "COMPLETE"
    job.last_heartbeat_at = datetime.now(UTC)


def mark_job_failure(job: ProcessingJob, error: Exception | str) -> None:
    job.error_message = str(error)
    job.completed_at = datetime.now(UTC)
    job.last_heartbeat_at = datetime.now(UTC)
    job.execution_status = "COMPLETE"
    if job.attempt >= job.max_attempts:
        job.state = JobState.DEAD_LETTER
        job.dead_letter_reason = "MAX_ATTEMPTS_EXHAUSTED"
        job.current_step = "재시도 한도를 초과해 dead-letter로 이동했습니다."
    else:
        job.state = JobState.FAILED
        job.next_attempt_at = datetime.now(UTC).replace(microsecond=0) + timedelta(seconds=job.retry_backoff_seconds)


def checkpoint(job: ProcessingJob) -> None:
    job.last_heartbeat_at = datetime.now(UTC)
    if job.cancel_requested:
        raise JobCancelled()


def complete_stage(job: ProcessingJob, key: str, state: JobState, current_step: str, completed: int) -> None:
    job.state = state
    job.current_step = current_step
    job.completed_units = completed
    for stage in job.stages:
        if stage["key"] == key:
            stage["state"] = "SUCCEEDED"
            stage["completed_at"] = now()
            break


class JobCancelled(Exception):
    pass


def ensure_job_is_active(job: ProcessingJob) -> None:
    checkpoint(job)


def fail_preparing_candidates(job: ProcessingJob, message: str) -> None:
    instance = INSTANCES.get(job.instance_id)
    if not instance:
        return
    for document_id in job.document_ids:
        document = instance.documents.get(document_id)
        if not document:
            continue
        for candidate_id in document.candidate_ids:
            candidate = CANDIDATES.get(candidate_id)
            if candidate and candidate.preparation_state == CandidateState.PREPARING:
                candidate.preparation_state = CandidateState.FAILED
                candidate.preparation_error = message
                candidate.prepared_at = datetime.now(UTC)


def run_processing_job(job_id: str, mode: PipelineMode, reuse_source_document_id: str | None = None) -> None:
    """Execute the local parser/candidate/index preparation outside the request."""
    try:
        with STATE_LOCK:
            job = JOBS.get(job_id)
            if not job or not claim_job_execution(job):
                return
            persist_state()
        with STATE_LOCK:
            job = JOBS[job_id]
            ensure_job_is_active(job)
            instance = get_instance(job.instance_id)
            job.state = JobState.PARSING
            job.current_step = "문서 구조를 읽고 있어요."
            for document_id in job.document_ids:
                instance.documents[document_id].parse_status = "PARSING"
            persist_state()

        with STATE_LOCK:
            job = JOBS[job_id]
            ensure_job_is_active(job)
            instance = get_instance(job.instance_id)
            for document_id in job.document_ids:
                document = instance.documents[document_id]
                parse_document_from_stored_source(instance, document)
            job.comparison_plans = {
                document_id: comparison_plan_payload(instance.documents[document_id])
                for document_id in job.document_ids
            }
            artifact = ARTIFACTS.get(job.artifact_id) if job.artifact_id else None
            if artifact:
                artifact.metadata["comparison_plans"] = job.comparison_plans
            complete_stage(job, "PARSING", JobState.GENERATING_CANDIDATES, "비교 후보를 준비하고 있어요.", 1)
            persist_state()

        with STATE_LOCK:
            job = JOBS[job_id]
            ensure_job_is_active(job)
            instance = get_instance(job.instance_id)
            reuse_source = reuse_source_for(instance, reuse_source_document_id) if mode == PipelineMode.REUSE else None
            if mode == PipelineMode.REUSE and not reuse_source:
                raise ValueError("재사용할 확정 파이프라인을 찾지 못했습니다.")
            for document_id in job.document_ids:
                document = instance.documents[document_id]
                if reuse_source:
                    _, source = reuse_source
                    reused = Candidate(
                        id=new_id(),
                        document_id=document.id,
                        chunking_strategy=source.chunking_strategy,
                        retrieval_config=source.retrieval_config,
                        friendly_name=source.friendly_name,
                        technical_description=source.technical_description,
                        is_temporary=False,
                        finalized=True,
                        selection_count=1,
                        chunking_parameters=source.chunking_parameters,
                        selection_reason=f"확정 파이프라인을 재사용했습니다. 원래 선택 근거: {source.selection_reason}",
                        segments=chunks_for_strategy(document, source.chunking_strategy, source.chunking_parameters),
                        estimated_chunk_count=document.candidate_chunk_counts.get(source.chunking_strategy, 0),
                        selected_chunk_count=document.candidate_chunk_counts.get(source.chunking_strategy, 0),
                        comparison_scope=ComparisonScope.FULL,
                    )
                    CANDIDATES[reused.id] = reused
                    document.candidate_ids.append(reused.id)
                    document.finalized_candidate_id = reused.id
                    instance.candidate_ids.append(reused.id)
                else:
                    create_candidates(instance, document)
            complete_stage(job, "CANDIDATES", JobState.INDEXING, "검색용 결과물을 준비하고 있어요.", 2)
            persist_state()

        with STATE_LOCK:
            job = JOBS[job_id]
            ensure_job_is_active(job)
            instance = get_instance(job.instance_id)
            ready_candidates = 0
            for document_id in job.document_ids:
                document = instance.documents[document_id]
                for candidate_id in document.candidate_ids:
                    candidate = CANDIDATES[candidate_id]
                    candidate.preparation_state = CandidateState.PREPARING
                    candidate.preparation_error = None
                    candidate.prepared_at = None
                    try:
                        prepare_candidate_index(instance, candidate)
                    except Exception as error:
                        candidate.preparation_state = CandidateState.FAILED
                        candidate.preparation_error = str(error)
                        candidate.prepared_at = datetime.now(UTC)
                    else:
                        candidate.preparation_state = CandidateState.READY
                        candidate.prepared_at = datetime.now(UTC)
                        ready_candidates += 1
                    persist_state()
            if not ready_candidates:
                raise RuntimeError("검색 후보를 하나도 준비하지 못했습니다.")
            complete_stage(job, "INDEXING", JobState.SUCCEEDED, "검색 준비가 완료되었어요.", 3)
            job.completed_at = datetime.now(UTC)
            complete_job_execution(job)
            instance.status = (
                InstanceStatus.READY
                if all(document.finalized_candidate_id for document in instance.documents.values())
                else InstanceStatus.TUNING
            )
            artifact = ARTIFACTS.get(job.artifact_id) if job.artifact_id else None
            if artifact:
                artifact.status = ArtifactStatus.READY
                artifact.updated_at = datetime.now(UTC)
                artifact.metadata["summary"] = "문서 파싱과 검색 준비가 완료되었습니다."
                artifact.metadata["comparison_plans"] = job.comparison_plans
                if job.kind == JobKind.REPARSE:
                    artifact.metadata["reparse_completed_at"] = now()
                    artifact.metadata["reparsed_provenance"] = {
                        document_id: {
                            "source": instance.documents[document_id].source_metadata,
                            "parser": instance.documents[document_id].parser_metadata,
                            "chunking": instance.documents[document_id].chunking_metadata,
                            "model": instance.documents[document_id].model_metadata,
                        }
                        for document_id in job.document_ids
                    }
            persist_state()
    except JobCancelled:
        with STATE_LOCK:
            job = JOBS.get(job_id)
            if job:
                job.state = JobState.CANCELLED
                job.current_step = "문서 준비를 중단했어요."
                job.completed_at = datetime.now(UTC)
                complete_job_execution(job)
                fail_preparing_candidates(job, "문서 준비가 중단되었습니다.")
                artifact = ARTIFACTS.get(job.artifact_id) if job.artifact_id else None
                if artifact:
                    artifact.status = ArtifactStatus.FAILED
                    artifact.metadata["cancelled"] = True
                    artifact.updated_at = datetime.now(UTC)
                persist_state()
    except Exception as error:  # pragma: no cover - defensive worker boundary
        with STATE_LOCK:
            job = JOBS.get(job_id)
            if job:
                job.current_step = "문서 준비를 마치지 못했어요."
                mark_job_failure(job, error)
                fail_preparing_candidates(job, "문서 준비 중 오류가 발생했습니다.")
                artifact = ARTIFACTS.get(job.artifact_id) if job.artifact_id else None
                if artifact:
                    artifact.status = ArtifactStatus.FAILED
                    artifact.updated_at = datetime.now(UTC)
                    if job.state == JobState.DEAD_LETTER:
                        artifact.metadata["dead_letter"] = {"reason": job.dead_letter_reason, "at": now()}
                persist_state()


def run_full_reindex_job(job_id: str) -> None:
    """Build the production-sized index after a sampled comparison is chosen."""
    try:
        with STATE_LOCK:
            job = JOBS.get(job_id)
            if not job or not claim_job_execution(job):
                return
            persist_state()
        with STATE_LOCK:
            job = JOBS[job_id]
            ensure_job_is_active(job)
            instance = get_instance(job.instance_id)
            job.state = JobState.GENERATING_CANDIDATES
            job.current_step = "확정된 설정으로 전체 문서를 다시 나누고 있어요."
            for document_id in job.document_ids:
                document = instance.documents[document_id]
                document.full_reindex_state = JobState.GENERATING_CANDIDATES
            persist_state()

        with STATE_LOCK:
            job = JOBS[job_id]
            ensure_job_is_active(job)
            instance = get_instance(job.instance_id)
            for document_id in job.document_ids:
                document = instance.documents[document_id]
                if not document.finalized_candidate_id:
                    raise ValueError("확정된 파이프라인이 없는 문서는 전체 재인덱싱할 수 없습니다.")
                candidate = CANDIDATES[document.finalized_candidate_id]
                full_segments = chunks_for_strategy(document, candidate.chunking_strategy, candidate.chunking_parameters)
                candidate.segments = full_segments
                candidate.preparation_state = CandidateState.PREPARING
                candidate.preparation_error = None
                candidate.prepared_at = None
            complete_stage(job, "FULL_CHUNKING", JobState.INDEXING, "전체 문서 검색 인덱스를 만들고 있어요.", 1)
            persist_state()

        with STATE_LOCK:
            job = JOBS[job_id]
            ensure_job_is_active(job)
            instance = get_instance(job.instance_id)
            for document_id in job.document_ids:
                document = instance.documents[document_id]
                candidate = CANDIDATES[document.finalized_candidate_id]
                prepare_candidate_index(instance, candidate)
                candidate.preparation_state = CandidateState.READY
                candidate.prepared_at = datetime.now(UTC)
                document.full_reindex_state = JobState.SUCCEEDED
            complete_stage(job, "FULL_INDEXING", JobState.SUCCEEDED, "전체 문서 재인덱싱이 완료되었어요.", 2)
            job.completed_at = datetime.now(UTC)
            complete_job_execution(job)
            artifact = ARTIFACTS.get(job.artifact_id) if job.artifact_id else None
            if artifact:
                artifact.status = ArtifactStatus.READY
                artifact.updated_at = datetime.now(UTC)
                artifact.metadata["summary"] = "확정된 설정으로 전체 문서 재인덱싱을 완료했습니다."
                artifact.metadata["indexed_chunk_counts"] = {
                    document_id: len(CANDIDATES[instance.documents[document_id].finalized_candidate_id].segments)
                    for document_id in job.document_ids
                }
            persist_state()
    except JobCancelled:
        with STATE_LOCK:
            job = JOBS.get(job_id)
            if job:
                job.state = JobState.CANCELLED
                job.current_step = "전체 문서 재인덱싱을 중단했어요."
                job.completed_at = datetime.now(UTC)
                complete_job_execution(job)
                instance = INSTANCES.get(job.instance_id)
                if instance:
                    for document_id in job.document_ids:
                        if document := instance.documents.get(document_id):
                            document.full_reindex_state = JobState.CANCELLED
                artifact = ARTIFACTS.get(job.artifact_id) if job.artifact_id else None
                if artifact:
                    artifact.status = ArtifactStatus.FAILED
                    artifact.metadata["cancelled"] = True
                    artifact.updated_at = datetime.now(UTC)
                persist_state()
    except Exception as error:  # pragma: no cover - defensive worker boundary
        with STATE_LOCK:
            job = JOBS.get(job_id)
            if job:
                job.current_step = "전체 문서 재인덱싱을 마치지 못했어요."
                mark_job_failure(job, error)
                instance = INSTANCES.get(job.instance_id)
                if instance:
                    for document_id in job.document_ids:
                        if document := instance.documents.get(document_id):
                            document.full_reindex_state = JobState.FAILED
                artifact = ARTIFACTS.get(job.artifact_id) if job.artifact_id else None
                if artifact:
                    artifact.status = ArtifactStatus.FAILED
                    artifact.updated_at = datetime.now(UTC)
                    artifact.metadata["error"] = str(error)
                    if job.state == JobState.DEAD_LETTER:
                        artifact.metadata["dead_letter"] = {"reason": job.dead_letter_reason, "at": now()}
                persist_state()


def dispatch_job(job: ProcessingJob, run: Callable[[], None]) -> None:
    """Record an adapter receipt before a worker can advance durable job state."""
    ensure_job_operational_fields(job)
    persist_state()
    receipt = dispatch(job.id, job.idempotency_key, run)
    job.dispatch_backend = receipt.backend
    job.dispatch_message_id = receipt.message_id
    job.dispatch_fallback_reason = receipt.fallback_reason
    # A local worker persists this receipt as part of its durable claim. Do not
    # contend for the lock here: a tiny test/document job must still be
    # observable as queued or running when the request returns.
    if receipt.backend != "thread":
        persist_state()


def start_processing_job(job: ProcessingJob, mode: PipelineMode, reuse_source_document_id: str | None = None) -> None:
    job.pipeline_mode = mode
    job.reuse_source_document_id = reuse_source_document_id
    dispatch_job(
        job,
        lambda: run_processing_job(job.id, job.pipeline_mode, job.reuse_source_document_id),
    )


def start_full_reindex_job(job: ProcessingJob) -> None:
    dispatch_job(job, lambda: run_full_reindex_job(job.id))


def consume_dispatched_job(job_id: str, idempotency_key: str) -> bool:
    """Worker adapter contract for Redis/SQS consumers.

    A consumer passes the two fields in the queue message. The durable claim in
    each runner makes duplicate delivery harmless and preserves the same work
    path used by the local thread fallback.
    """
    with STATE_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return False
        ensure_job_operational_fields(job)
        if job.idempotency_key != idempotency_key:
            return False
    if job.kind == JobKind.FULL_REINDEX:
        run_full_reindex_job(job.id)
    else:
        run_processing_job(job.id, job.pipeline_mode, job.reuse_source_document_id)
    return True


def resume_pending_jobs() -> None:
    for job in list(JOBS.values()):
        if job.state not in {JobState.QUEUED, JobState.PARSING, JobState.GENERATING_CANDIDATES, JobState.INDEXING}:
            continue
        instance = INSTANCES.get(job.instance_id)
        if not instance or not job.document_ids:
            continue
        if not instance.documents.get(job.document_ids[0]):
            continue
        if job.kind == JobKind.FULL_REINDEX:
            start_full_reindex_job(job)
        else:
            start_processing_job(job, job.pipeline_mode, job.reuse_source_document_id)


restore_state()
resume_pending_jobs()


def reuse_source_for(instance: RagInstance, requested_document_id: str | None) -> tuple[Document, Candidate] | None:
    documents = [instance.documents.get(requested_document_id)] if requested_document_id else list(instance.documents.values())
    for document in documents:
        if document and document.finalized_candidate_id:
            return document, CANDIDATES[document.finalized_candidate_id]
    return None


def schedule_full_reindex(instance: RagInstance, document: Document) -> tuple[ProcessingJob, Artifact] | None:
    """Persist and enqueue full indexing only when tuning used a bounded sample."""
    if document.comparison_scope != ComparisonScope.SAMPLE:
        return None
    artifact = register_artifact(
        instance,
        type="FULL_REINDEX",
        title=f"{document.filename} 전체 문서 재인덱싱",
        context_document_ids=[document.id],
        metadata={
            "context_status": "AVAILABLE",
            "summary": "샘플 비교에서 선택한 설정으로 전체 문서를 재인덱싱할 예정입니다.",
            "comparison": comparison_plan_payload(document),
            "selected_pipeline_id": document.finalized_candidate_id,
        },
        artifact_status=ArtifactStatus.PROCESSING,
    )
    job = ProcessingJob(
        id=new_id(),
        instance_id=instance.id,
        document_ids=[document.id],
        state=JobState.QUEUED,
        current_step="전체 문서 재인덱싱을 시작할 예정이에요.",
        completed_units=0,
        total_units=2,
        created_at=datetime.now(UTC),
        stages=full_reindex_stages(),
        artifact_id=artifact.id,
        pipeline_mode=document.pipeline_mode,
        kind=JobKind.FULL_REINDEX,
        comparison_plans={document.id: comparison_plan_payload(document)},
    )
    JOBS[job.id] = job
    document.full_reindex_job_id = job.id
    document.full_reindex_state = JobState.QUEUED
    persist_state()
    start_full_reindex_job(job)
    return job, artifact


@app.post(f"{API_PREFIX}/rag-instances/{{instance_id}}/documents", status_code=status.HTTP_202_ACCEPTED)
def upload_documents(instance_id: str, body: DocumentsCreate) -> dict:
    instance = get_instance(instance_id)
    mode = resolved_pipeline_mode(body)
    reuse_source = reuse_source_for(instance, body.reuse_from_document_id) if mode == PipelineMode.REUSE else None
    if mode == PipelineMode.REUSE and not reuse_source:
        raise HTTPException(409, detail={"code": "NO_FINALIZED_PIPELINE_TO_REUSE", "message": "재사용할 확정 파이프라인이 없습니다. 이 문서를 따로 튜닝해 주세요."})
    created: list[Document] = []
    for item in body.documents:
        if not item.content and not item.content_base64:
            raise HTTPException(422, detail={"code": "DOCUMENT_CONTENT_REQUIRED", "message": "문서 본문 또는 파일 데이터를 함께 보내 주세요."})
        document = Document(
            id=new_id(),
            filename=item.filename,
            content_type=item.content_type,
            content=item.content or "",
            segments=[],
            raw_content_base64=item.content_base64,
            parse_status="UPLOADED",
        )
        document.pipeline_mode = mode
        try:
            store_document_source(instance, document, decode_source(item.content, item.content_base64))
        except SourceStorageError as error:
            raise HTTPException(
                503,
                detail={"code": "SOURCE_STORAGE_UNAVAILABLE", "message": "원본 파일을 재현 가능 저장소에 보관하지 못했습니다.", "details": {"error": str(error)}},
            ) from error
        # Text uploads can expose their comparison cost immediately. Binary
        # sources are authoritatively recalculated after the async parser runs.
        if item.content:
            document.segments = split_segments(item.content)
            document.chunking_analysis = analyze_document_for_chunking(document)
            document.profile = document_profile(document, document.chunking_analysis)
            configure_comparison_scope(document)
        instance.documents[document.id] = document
        created.append(document)
    instance.status = InstanceStatus.SETTING_UP
    artifact = register_artifact(
        instance,
        type="PROCESSING_RUN",
        title="문서 준비 작업",
        context_document_ids=[item.id for item in created],
        metadata={
            "pipeline_mode": mode,
            "context_status": "AVAILABLE",
            "summary": "문서 준비를 시작했어요.",
            "comparison_plans": {document.id: comparison_plan_payload(document) for document in created},
            "sources": {document.id: document.source_metadata for document in created},
        },
        artifact_status=ArtifactStatus.PROCESSING,
    )
    job = ProcessingJob(
        id=new_id(),
        instance_id=instance.id,
        document_ids=[item.id for item in created],
        state=JobState.QUEUED,
        current_step="문서 준비를 시작할 예정이에요.",
        completed_units=0,
        total_units=3,
        created_at=datetime.now(UTC),
        stages=job_stages(mode),
        artifact_id=artifact.id,
        pipeline_mode=mode,
        reuse_source_document_id=reuse_source[0].id if reuse_source else None,
        comparison_plans={document.id: comparison_plan_payload(document) for document in created},
    )
    JOBS[job.id] = job
    for document in created:
        document.processing_job_id = job.id
    decision = {
        "pipeline_mode": mode,
        "next_action": "TUNE_DOCUMENT" if mode == PipelineMode.RETUNE else "SEARCH_READY",
        "reuse_source_document_id": reuse_source[0].id if reuse_source else None,
        "message": "답변 비교를 시작해 이 문서에 맞는 설정을 고르세요." if mode == PipelineMode.RETUNE else "기존에 확정한 설정을 적용했습니다. 바로 검색할 수 있습니다.",
        "comparison_scope": ComparisonScope.SAMPLE if any(document.comparison_scope == ComparisonScope.SAMPLE for document in created) else ComparisonScope.FULL,
        "estimated_chunk_count": max((document.estimated_chunk_count for document in created), default=0),
        "selected_chunk_count": max((document.selected_chunk_count for document in created), default=0),
        "comparison_plans": {document.id: comparison_plan_payload(document) for document in created},
    }
    persist_state()
    start_processing_job(job, mode, reuse_source[0].id if reuse_source else None)
    return {"job": job_payload(job), "artifact": artifact_payload(artifact), "decision": decision, "documents": [document_payload(item) for item in created]}


@app.post(f"{API_PREFIX}/rag-instances/{{instance_id}}/documents/{{document_id}}/reparse", status_code=status.HTTP_202_ACCEPTED)
def reparse_document(instance_id: str, document_id: str, body: ReparseRequest) -> dict:
    """Re-run parser/candidate preparation from the immutable stored source."""
    instance = get_instance(instance_id)
    document = instance.documents.get(document_id)
    if not document:
        raise not_found("문서")
    if not document.source_metadata.get("storage_key"):
        raise HTTPException(
            409,
            detail={"code": "SOURCE_PROVENANCE_UNAVAILABLE", "message": "이 레거시 문서에는 재현 가능한 원본 저장소 참조가 없습니다. 원본 파일을 다시 업로드해 주세요."},
        )
    if document.processing_job_id:
        active = JOBS.get(document.processing_job_id)
        if active and active.state in {JobState.QUEUED, JobState.PARSING, JobState.GENERATING_CANDIDATES, JobState.INDEXING}:
            raise HTTPException(409, detail={"code": "DOCUMENT_PROCESSING", "message": "이미 문서 처리 작업이 진행 중입니다."})
    baseline = {
        "version": SOURCE_PROVENANCE_VERSION,
        "captured_at": now(),
        "document": document_payload(document),
        "reason": body.reason,
    }
    baseline_artifact = register_artifact(
        instance,
        type="REPARSE_BASELINE",
        title=f"{document.filename} 재파싱 전 기준선",
        context_document_ids=[document.id],
        metadata={"context_status": "AVAILABLE", "summary": "기존 원본·parser·chunking·model provenance를 보존했습니다."},
        payload=baseline,
    )
    for candidate_id in list(document.candidate_ids):
        CANDIDATES.pop(candidate_id, None)
        if candidate_id in instance.candidate_ids:
            instance.candidate_ids.remove(candidate_id)
    document.candidate_ids = []
    document.finalized_candidate_id = None
    document.full_reindex_job_id = None
    document.full_reindex_state = None
    document.pipeline_mode = PipelineMode.RETUNE
    document.parse_status = "UPLOADED"
    document.segments = []
    instance.status = InstanceStatus.SETTING_UP
    artifact = register_artifact(
        instance,
        type="REPARSE_RUN",
        title=f"{document.filename} 원본 재파싱",
        context_document_ids=[document.id],
        metadata={
            "context_status": "AVAILABLE",
            "reason": body.reason,
            "baseline_artifact_id": baseline_artifact.id,
            "source": document.source_metadata,
            "summary": "저장된 원본 파일로 parser와 검색 후보를 다시 준비하고 있어요.",
        },
        artifact_status=ArtifactStatus.PROCESSING,
    )
    job = ProcessingJob(
        id=new_id(),
        instance_id=instance.id,
        document_ids=[document.id],
        state=JobState.QUEUED,
        current_step="저장된 원본 파일 재파싱을 시작할 예정이에요.",
        completed_units=0,
        total_units=3,
        created_at=datetime.now(UTC),
        stages=job_stages(PipelineMode.RETUNE),
        artifact_id=artifact.id,
        pipeline_mode=PipelineMode.RETUNE,
        kind=JobKind.REPARSE,
        comparison_plans={document.id: comparison_plan_payload(document)},
    )
    JOBS[job.id] = job
    document.processing_job_id = job.id
    persist_state()
    start_processing_job(job, PipelineMode.RETUNE)
    return {
        "job": job_payload(job),
        "artifact": artifact_payload(artifact),
        "baseline_artifact": artifact_payload(baseline_artifact),
        "document": document_payload(document),
        "next_action": "TUNE_DOCUMENT",
    }


def job_has_failed_candidates(job: ProcessingJob) -> bool:
    instance = INSTANCES.get(job.instance_id)
    if not instance:
        return False
    return any(
        candidate is not None and candidate.preparation_state == CandidateState.FAILED
        for document_id in job.document_ids
        for document in [instance.documents.get(document_id)]
        if document is not None
        for candidate_id in document.candidate_ids
        for candidate in [CANDIDATES.get(candidate_id)]
    )


def job_can_retry(job: ProcessingJob) -> bool:
    ensure_job_operational_fields(job)
    if job.state == JobState.DEAD_LETTER or job.attempt >= job.max_attempts:
        return False
    if job.next_attempt_at and job.next_attempt_at > datetime.now(UTC):
        return False
    return job.state in {JobState.FAILED, JobState.CANCELLED} or job_has_failed_candidates(job)


def job_payload(job: ProcessingJob) -> dict:
    ensure_job_operational_fields(job)
    return {
        "id": job.id, "instance_id": job.instance_id, "document_ids": job.document_ids,
        "kind": job.kind, "state": job.state, "current_step": job.current_step,
        "progress": {"completed": job.completed_units, "total": job.total_units},
        "stages": job.stages, "artifact_id": job.artifact_id, "comparison_plans": job.comparison_plans,
        "can_retry": job_can_retry(job), "can_recover": job.state == JobState.DEAD_LETTER,
        "can_cancel": job.state in {JobState.QUEUED, JobState.PARSING, JobState.GENERATING_CANDIDATES, JobState.INDEXING},
        "attempt": job.attempt, "queue_backend": backend_name(),
        "created_at": job.created_at.isoformat(), "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message,
        "operational": {
            "idempotency_key": job.idempotency_key,
            "dispatch": {"backend": job.dispatch_backend, "message_id": job.dispatch_message_id, "fallback_reason": job.dispatch_fallback_reason},
            "execution": {"status": job.execution_status, "count": job.execution_count, "worker_id": job.worker_id, "last_heartbeat_at": job.last_heartbeat_at.isoformat() if job.last_heartbeat_at else None},
            "retry": {"max_attempts": job.max_attempts, "backoff_seconds": job.retry_backoff_seconds, "next_attempt_at": job.next_attempt_at.isoformat() if job.next_attempt_at else None},
            "dead_letter_reason": job.dead_letter_reason,
        },
    }


@app.get(f"{API_PREFIX}/job-platform")
def job_platform() -> dict:
    states = Counter(str(job.state) for job in JOBS.values())
    workers = sorted(
        ({"worker_id": job.worker_id, "last_heartbeat_at": job.last_heartbeat_at.isoformat() if job.last_heartbeat_at else None, "job_id": job.id}
         for job in JOBS.values() if job.worker_id),
        key=lambda item: item["last_heartbeat_at"] or "", reverse=True,
    )
    return {
        "queue": queue_observability(),
        "jobs_by_state": dict(states),
        "dead_letter_count": states.get(str(JobState.DEAD_LETTER), 0),
        "workers": workers,
    }


@app.get(f"{API_PREFIX}/rag-jobs/dead-letters")
def list_dead_letters() -> dict:
    jobs = sorted((job for job in JOBS.values() if job.state == JobState.DEAD_LETTER), key=lambda job: job.completed_at or job.created_at, reverse=True)
    return {"items": [job_payload(job) for job in jobs], "total": len(jobs)}


@app.get(f"{API_PREFIX}/rag-jobs/{{job_id}}")
def get_job(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if not job:
        raise not_found("작업")
    return job_payload(job)


@app.post(f"{API_PREFIX}/rag-jobs/{{job_id}}/cancel")
def cancel_job(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if not job:
        raise not_found("작업")
    if job.state not in {JobState.QUEUED, JobState.PARSING, JobState.GENERATING_CANDIDATES, JobState.INDEXING}:
        raise HTTPException(409, detail={"code": "JOB_NOT_CANCELLABLE", "message": "완료된 작업은 중단할 수 없습니다."})
    job.cancel_requested = True
    job.current_step = "중단 요청을 확인하고 있어요."
    persist_state()
    return job_payload(job)


@app.post(f"{API_PREFIX}/rag-jobs/{{job_id}}/retry")
def retry_job(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if not job:
        raise not_found("작업")
    ensure_job_operational_fields(job)
    if job.state == JobState.DEAD_LETTER:
        raise HTTPException(409, detail={"code": "JOB_IN_DEAD_LETTER", "message": "dead-letter 작업은 복구 API로 다시 실행할 수 있습니다."})
    if job.next_attempt_at and job.next_attempt_at > datetime.now(UTC):
        raise HTTPException(409, detail={"code": "JOB_RETRY_BACKOFF", "message": "설정된 재시도 대기 시간이 끝난 뒤 다시 시도할 수 있습니다.", "next_attempt_at": job.next_attempt_at.isoformat()})
    if job.attempt >= job.max_attempts:
        mark_job_failure(job, job.error_message or "재시도 한도를 초과했습니다.")
        persist_state()
        raise HTTPException(409, detail={"code": "JOB_RETRY_LIMIT", "message": "재시도 한도를 초과해 dead-letter로 이동했습니다."})
    if job.state not in {JobState.FAILED, JobState.CANCELLED} and not job_has_failed_candidates(job):
        raise HTTPException(409, detail={"code": "JOB_NOT_RETRYABLE", "message": "실패·중단되었거나 후보 준비에 실패한 작업만 다시 시도할 수 있습니다."})
    instance = get_instance(job.instance_id)
    if job.kind == JobKind.FULL_REINDEX:
        for document_id in job.document_ids:
            if document := instance.documents.get(document_id):
                document.full_reindex_state = JobState.QUEUED
        job.state = JobState.QUEUED
        job.current_step = "전체 문서 재인덱싱을 다시 시작할 예정이에요."
        job.completed_units = 0
        job.completed_at = None
        job.error_message = None
        job.cancel_requested = False
        job.attempt += 1
        job.next_attempt_at = None
        job.dead_letter_reason = None
        job.execution_status = "IDLE"
        job.stages = full_reindex_stages()
        persist_state()
        start_full_reindex_job(job)
        return job_payload(job)
    for round_id, round_ in list(ROUNDS.items()):
        if round_.instance_id == instance.id and set(round_.document_ids) & set(job.document_ids):
            ROUNDS.pop(round_id)
    for document_id in job.document_ids:
        document = instance.documents.get(document_id)
        if not document:
            continue
        for candidate_id in list(document.candidate_ids):
            candidate = CANDIDATES.get(candidate_id)
            if candidate and candidate.finalized:
                continue
            CANDIDATES.pop(candidate_id, None)
            if candidate_id in instance.candidate_ids:
                instance.candidate_ids.remove(candidate_id)
            document.candidate_ids.remove(candidate_id)
        document.segments = []
        document.parse_status = "UPLOADED"
    job.state = JobState.QUEUED
    job.current_step = "문서 준비를 다시 시작할 예정이에요."
    job.completed_units = 0
    job.completed_at = None
    job.error_message = None
    job.cancel_requested = False
    job.attempt += 1
    job.next_attempt_at = None
    job.dead_letter_reason = None
    job.execution_status = "IDLE"
    job.stages = job_stages(job.pipeline_mode)
    persist_state()
    start_processing_job(job, job.pipeline_mode, job.reuse_source_document_id)
    return job_payload(job)


@app.post(f"{API_PREFIX}/rag-jobs/{{job_id}}/recover")
def recover_dead_letter(job_id: str) -> dict:
    """Operator-only recovery resets the retry budget and reuses the normal path."""
    job = JOBS.get(job_id)
    if not job:
        raise not_found("작업")
    if job.state != JobState.DEAD_LETTER:
        raise HTTPException(409, detail={"code": "JOB_NOT_DEAD_LETTER", "message": "dead-letter 상태의 작업만 복구할 수 있습니다."})
    job.state = JobState.FAILED
    job.attempt = 0
    job.dead_letter_reason = None
    job.next_attempt_at = None
    job.execution_status = "IDLE"
    job.current_step = "운영자가 dead-letter 작업 복구를 요청했어요."
    persist_state()
    return retry_job(job_id)


@app.get(f"{API_PREFIX}/rag-instances/{{instance_id}}/jobs")
def list_jobs(instance_id: str) -> dict:
    get_instance(instance_id)
    jobs = sorted((job for job in JOBS.values() if job.instance_id == instance_id), key=lambda job: job.created_at, reverse=True)
    return {"items": [job_payload(job) for job in jobs], "total": len(jobs)}


@app.get(f"{API_PREFIX}/rag-instances/{{instance_id}}/document-add-options")
def document_add_options(instance_id: str) -> dict:
    instance = get_instance(instance_id)
    reusable = [
        {"document_id": document.id, "filename": document.filename, "pipeline": candidate_payload(CANDIDATES[document.finalized_candidate_id])}
        for document in instance.documents.values()
        if document.finalized_candidate_id
    ]
    return {
        "modes": [
            {"id": PipelineMode.REUSE, "label": "기존 설정 적용", "enabled": bool(reusable), "description": "이미 검증한 청킹·검색 설정을 바로 적용합니다."},
            {"id": PipelineMode.RETUNE, "label": "이 문서 따로 튜닝", "enabled": True, "description": "답변을 비교해서 이 문서만의 설정을 새로 고릅니다."},
        ],
        "reusable_sources": reusable,
        "default_mode": PipelineMode.REUSE if reusable else PipelineMode.RETUNE,
    }


def latest_retuning_run(instance: RagInstance, document_ids: list[str]) -> Artifact | None:
    expected = set(document_ids)
    runs = [
        artifact
        for artifact_id in instance.artifact_ids
        for artifact in [ARTIFACTS.get(artifact_id)]
        if artifact
        and artifact.type == "RETUNING_RUN"
        and set(artifact.context_document_ids) == expected
        and artifact.metadata.get("baseline_artifact_id")
    ]
    return max(runs, key=lambda artifact: artifact.created_at) if runs else None


def retuning_comparison_observations(results: list[dict]) -> dict:
    """Comparable facts from a retune comparison, deliberately not a quality score."""
    generation = [result.get("generation", {}) for result in results]
    return {
        "candidate_count": len(results),
        "ready_count": sum(result.get("candidate_state") == CandidateState.READY for result in results),
        "no_evidence_count": sum(result.get("candidate_state") == CandidateState.NO_EVIDENCE for result in results),
        "grounded_count": sum(bool(result.get("grounded")) for result in results),
        "fallback_count": sum(bool(item.get("fallback")) for item in generation),
        "citation_count": sum(len(result.get("citations", [])) for result in results),
        "providers": sorted({item.get("provider") for item in generation if item.get("provider")}),
        "interpretation": "후보 비교에서 관찰된 검색·grounding 사실이며, 모델 품질 순위나 개선 보장은 아닙니다.",
    }


def create_retuning_outcome_artifact(
    instance: RagInstance,
    document_ids: list[str],
    round_: ComparisonRound,
    results: list[dict],
) -> Artifact | None:
    retuning_run = latest_retuning_run(instance, document_ids)
    if not retuning_run:
        return None
    baseline_id = retuning_run.metadata["baseline_artifact_id"]
    baseline = ARTIFACTS.get(baseline_id)
    if not baseline:
        return None
    observations = retuning_comparison_observations(results)
    outcome = register_artifact(
        instance,
        type="RETUNING_OUTCOME",
        title="재튜닝 비교 결과",
        context_document_ids=document_ids,
        metadata={
            "context_status": "AVAILABLE",
            "baseline_artifact_id": baseline_id,
            "retuning_run_artifact_id": retuning_run.id,
            "round_id": round_.id,
            "signal_version": RETUNING_SIGNAL_VERSION,
            "selection_state": "PENDING_USER_VOTE",
            "summary": "기준선과 새 후보의 관측값을 함께 저장했습니다. 사용자 투표와 확정 전에는 개선을 주장하지 않습니다.",
            "comparison_observations": observations,
        },
        payload={
            "baseline": baseline.payload,
            "question": round_.question,
            "comparison_observations": observations,
            "candidates": [
                {
                    "candidate": result["candidate"],
                    "candidate_state": result["candidate_state"],
                    "relevance": result["relevance"],
                    "grounded": result["grounded"],
                    "citation_count": len(result.get("citations", [])),
                    "generation": result.get("generation", {}),
                }
                for result in results
            ],
        },
    )
    retuning_run.metadata["outcome_artifact_id"] = outcome.id
    retuning_run.updated_at = datetime.now(UTC)
    return outcome


def candidate_exploration_payload(exploration: CandidateExploration) -> dict:
    pool = [candidate_payload(CANDIDATES[candidate_id]) for candidate_id in exploration.candidate_pool_ids if candidate_id in CANDIDATES]
    proposals = []
    for proposal in exploration.proposals:
        candidate = CANDIDATES.get(proposal.get("candidate_id"))
        proposals.append({**proposal, "candidate": candidate_payload(candidate) if candidate else None})
    return {
        "id": exploration.id,
        "instance_id": exploration.instance_id,
        "document_ids": exploration.document_ids,
        "question": exploration.question,
        "status": exploration.status,
        "created_at": exploration.created_at.isoformat(),
        "pool": pool,
        "pool_candidate_ids": exploration.candidate_pool_ids,
        "narrowed_candidate_ids": exploration.narrowed_candidate_ids,
        "proposed": proposals,
        "rationale": exploration.rationale,
        "ledger": exploration.ledger,
        "rollback": {
            "supported": True,
            "status": exploration.status,
            "restore_supported": exploration.status == ExplorationStatus.ROLLED_BACK,
            "note": "제안 후보만 보관/복원하며 기존 후보·투표·확정 결과를 자동 변경하지 않습니다.",
        },
        "selection": {
            "automatic": False,
            "finalized_candidate_ids": [
                instance_document.finalized_candidate_id
                for instance_document in get_instance(exploration.instance_id).documents.values()
                if instance_document.finalized_candidate_id
            ],
            "message": "탐색은 후보 제안과 관측 기록만 수행합니다. 비교·투표·확정은 기존 명시적 흐름으로 진행하세요.",
        },
        "artifact_id": exploration.artifact_id,
    }


def exploration_source_provenance(instance: RagInstance, document_ids: list[str]) -> dict:
    return {
        document_id: {
            "source": instance.documents[document_id].source_metadata,
            "parser": instance.documents[document_id].parser_metadata,
            "chunking": instance.documents[document_id].chunking_metadata,
            "model": instance.documents[document_id].model_metadata,
        }
        for document_id in document_ids
    }


@app.post(f"{API_PREFIX}/rag-instances/{{instance_id}}/candidate-exploration", status_code=status.HTTP_201_CREATED)
def start_candidate_exploration(instance_id: str, body: CandidateExplorationRequest) -> dict:
    instance = get_instance(instance_id)
    missing = [document_id for document_id in body.document_ids if document_id not in instance.documents]
    if missing:
        raise HTTPException(422, detail={"code": "DOCUMENT_NOT_IN_INSTANCE", "message": "선택한 문서가 이 RAG에 없습니다.", "details": {"document_ids": missing}})
    pool_candidates = [
        CANDIDATES[candidate_id]
        for document_id in body.document_ids
        for candidate_id in instance.documents[document_id].candidate_ids
        if candidate_id in CANDIDATES and not CANDIDATES[candidate_id].archived
    ]
    if not pool_candidates:
        raise HTTPException(409, detail={"code": "EXPLORATION_POOL_EMPTY", "message": "탐색할 준비된 후보 풀이 없습니다. 문서 처리가 끝난 뒤 다시 시도하세요."})
    signal_map = {candidate.id: exploration_signals(candidate) for candidate in pool_candidates}
    ranked = sorted(pool_candidates, key=lambda candidate: (-signal_map[candidate.id]["priority"], candidate.id))
    narrowed: list[Candidate] = []
    # Give every requested document one transparent chance before filling the
    # remaining bounded exploration budget.
    for document_id in body.document_ids:
        candidate = next((item for item in ranked if item.document_id == document_id), None)
        if candidate and candidate not in narrowed:
            narrowed.append(candidate)
    for candidate in ranked:
        if len(narrowed) >= body.max_proposals:
            break
        if candidate not in narrowed:
            narrowed.append(candidate)
    narrowed = narrowed[:body.max_proposals]
    exploration = CandidateExploration(
        id=new_id(),
        instance_id=instance.id,
        document_ids=body.document_ids,
        created_at=datetime.now(UTC),
        question=body.question,
        max_proposals=body.max_proposals,
        candidate_pool_ids=[candidate.id for candidate in pool_candidates],
        narrowed_candidate_ids=[candidate.id for candidate in narrowed],
        rationale=[
            {
                "candidate_id": candidate.id,
                "signals": signal_map[candidate.id],
                "reason": "준비 상태·기존 사용자 투표·비교 근거 관측값을 기준으로 제한된 탐색 풀에 포함했습니다.",
            }
            for candidate in ranked
        ],
        ledger=[{"at": now(), "event": "POOL_EVALUATED", "candidate_count": len(pool_candidates), "max_proposals": body.max_proposals}],
    )
    for parent in narrowed:
        document = instance.documents[parent.document_id]
        parameters, retrieval, chunking_reason = exploration_variant(parent)
        proposal = {
            "parent_candidate_id": parent.id,
            "base_friendly_name": parent.friendly_name,
            "document_id": document.id,
            "chunking_strategy": parent.chunking_strategy,
            "chunking_parameters": parameters,
            "retrieval_config": retrieval,
            "selection_reason": f"탐색 제안: {chunking_reason} 검색은 {parent.retrieval_config}에서 {retrieval}로만 바꿔 비교합니다.",
            "technical_description": f"Adaptive exploration variant of {parent.id}: {chunking_reason}",
            "rationale": {
                "parent_signals": signal_map[parent.id],
                "parameter_change_reason": chunking_reason,
                "retrieval_change": {"from": parent.retrieval_config, "to": retrieval},
                "automatic_selection": False,
            },
        }
        create_exploration_candidate(instance, document, proposal, exploration.id)
        exploration.proposals.append(proposal)
    exploration.ledger.append({"at": now(), "event": "PROPOSALS_CREATED", "proposal_candidate_ids": [proposal["candidate_id"] for proposal in exploration.proposals]})
    artifact = register_artifact(
        instance,
        type="ADAPTIVE_EXPLORATION",
        title="적응형 후보 탐색",
        context_document_ids=body.document_ids,
        metadata={
            "context_status": "AVAILABLE",
            "exploration_id": exploration.id,
            "signal_version": "adaptive-exploration.v1",
            "automatic_selection": False,
            "summary": "후보 풀의 제한된 운영·비교 신호를 기록해 변형 후보를 제안했습니다. 이 기록은 품질 순위나 자동 확정이 아닙니다.",
            "source_provenance": exploration_source_provenance(instance, body.document_ids),
        },
        payload={"candidate_exploration": candidate_exploration_payload(exploration)},
    )
    exploration.artifact_id = artifact.id
    artifact.payload["candidate_exploration"] = candidate_exploration_payload(exploration)
    EXPLORATIONS[exploration.id] = exploration
    persist_state()
    return {"candidate_exploration": candidate_exploration_payload(exploration), "artifact": artifact_payload(artifact)}


@app.get(f"{API_PREFIX}/rag-instances/{{instance_id}}/candidate-exploration")
def list_candidate_explorations(instance_id: str) -> dict:
    get_instance(instance_id)
    items = sorted((item for item in EXPLORATIONS.values() if item.instance_id == instance_id), key=lambda item: item.created_at, reverse=True)
    return {"items": [candidate_exploration_payload(item) for item in items], "total": len(items)}


@app.get(f"{API_PREFIX}/candidate-exploration/{{exploration_id}}")
def get_candidate_exploration(exploration_id: str) -> dict:
    exploration = EXPLORATIONS.get(exploration_id)
    if not exploration:
        raise not_found("후보 탐색")
    return {"candidate_exploration": candidate_exploration_payload(exploration)}


@app.post(f"{API_PREFIX}/candidate-exploration/{{exploration_id}}/rollback")
def rollback_candidate_exploration(exploration_id: str) -> dict:
    exploration = EXPLORATIONS.get(exploration_id)
    if not exploration:
        raise not_found("후보 탐색")
    if exploration.status == ExplorationStatus.ROLLED_BACK:
        raise HTTPException(409, detail={"code": "EXPLORATION_ALREADY_ROLLED_BACK", "message": "이미 롤백된 탐색입니다."})
    instance = get_instance(exploration.instance_id)
    archived_ids = []
    for proposal in exploration.proposals:
        candidate = CANDIDATES.get(proposal.get("candidate_id"))
        if not candidate or candidate.exploration_round_id != exploration.id:
            continue
        candidate.archived = True
        document = instance.documents.get(candidate.document_id)
        if document and candidate.id in document.candidate_ids:
            document.candidate_ids.remove(candidate.id)
        if candidate.id in instance.candidate_ids:
            instance.candidate_ids.remove(candidate.id)
        archived_ids.append(candidate.id)
    exploration.status = ExplorationStatus.ROLLED_BACK
    exploration.ledger.append({"at": now(), "event": "ROLLED_BACK", "candidate_ids": archived_ids, "automatic_selection": False})
    if exploration.artifact_id and (artifact := ARTIFACTS.get(exploration.artifact_id)):
        artifact.metadata["status"] = "ROLLED_BACK"
        artifact.metadata["rollback_candidate_ids"] = archived_ids
        artifact.updated_at = datetime.now(UTC)
    persist_state()
    return {"candidate_exploration": candidate_exploration_payload(exploration), "archived_candidate_ids": archived_ids}


@app.post(f"{API_PREFIX}/candidate-exploration/{{exploration_id}}/restore")
def restore_candidate_exploration(exploration_id: str) -> dict:
    exploration = EXPLORATIONS.get(exploration_id)
    if not exploration:
        raise not_found("후보 탐색")
    if exploration.status != ExplorationStatus.ROLLED_BACK:
        raise HTTPException(409, detail={"code": "EXPLORATION_NOT_ROLLED_BACK", "message": "롤백된 탐색만 복원할 수 있습니다."})
    instance = get_instance(exploration.instance_id)
    restored_ids = []
    for proposal in exploration.proposals:
        candidate = CANDIDATES.get(proposal.get("candidate_id"))
        if candidate and candidate.exploration_round_id == exploration.id:
            candidate.archived = False
            document = instance.documents.get(candidate.document_id)
            if document and candidate.id not in document.candidate_ids:
                document.candidate_ids.append(candidate.id)
            if candidate.id not in instance.candidate_ids:
                instance.candidate_ids.append(candidate.id)
            restored_ids.append(candidate.id)
            continue
        document = instance.documents.get(proposal["document_id"])
        if not document:
            continue
        restored = create_exploration_candidate(instance, document, proposal, exploration.id)
        restored_ids.append(restored.id)
    exploration.status = ExplorationStatus.RESTORED
    exploration.ledger.append({"at": now(), "event": "RESTORED", "candidate_ids": restored_ids, "automatic_selection": False})
    if exploration.artifact_id and (artifact := ARTIFACTS.get(exploration.artifact_id)):
        artifact.metadata["status"] = "RESTORED"
        artifact.updated_at = datetime.now(UTC)
    persist_state()
    return {"candidate_exploration": candidate_exploration_payload(exploration), "restored_candidate_ids": restored_ids}


@app.post(f"{API_PREFIX}/rag-instances/{{instance_id}}/tuning/compare")
def compare_candidates(instance_id: str, body: CompareRequest) -> dict:
    instance = get_instance(instance_id)
    missing = [document_id for document_id in body.document_ids if document_id not in instance.documents]
    if missing:
        raise HTTPException(422, detail={"code": "DOCUMENT_NOT_IN_INSTANCE", "message": "선택한 문서가 이 RAG에 없습니다.", "details": {"document_ids": missing}})
    candidate_ids = [
        candidate_id
        for document_id in body.document_ids
        for candidate_id in instance.documents[document_id].candidate_ids
        if candidate_id in CANDIDATES and not CANDIDATES[candidate_id].archived
    ]
    round_ = ComparisonRound(id=new_id(), instance_id=instance.id, document_ids=body.document_ids, question=body.question, candidate_ids=candidate_ids, created_at=datetime.now(UTC))
    ROUNDS[round_.id] = round_
    results = comparison_results(instance, round_)
    generation_results = [result.get("generation", {}) for result in results]
    artifact = register_artifact(
        instance,
        type="TUNING_COMPARISON",
        title=f"비교 라운드 · {body.question[:48]}",
        context_document_ids=body.document_ids,
        metadata={
            "round_id": round_.id,
            "candidate_count": len(candidate_ids),
            "context_status": "AVAILABLE",
            "view": "answer_with_inline_citations",
            "generation": {
                "providers": sorted({item.get("provider") for item in generation_results if item.get("provider")}),
                "fallback_count": sum(1 for item in generation_results if item.get("fallback")),
                "grounding_valid": all(item.get("grounding_valid", False) for item in generation_results if item),
            },
        },
        payload={"question": body.question, "candidate_ids": candidate_ids},
    )
    retuning_outcome = create_retuning_outcome_artifact(instance, body.document_ids, round_, results)
    persist_state()
    return {
        "round": round_payload(round_),
        "artifact": artifact_payload(artifact),
        "retuning_outcome_artifact": artifact_payload(retuning_outcome) if retuning_outcome else None,
        "results": results,
        "view": {"default": "answer_with_inline_citations", "alternate": "source_chunks"},
    }


def round_payload(round_: ComparisonRound) -> dict:
    return {
        "id": round_.id,
        "instance_id": round_.instance_id,
        "document_ids": round_.document_ids,
        "question": round_.question,
        "candidate_ids": round_.candidate_ids,
        "selected_candidate_ids": round_.selected_candidate_ids,
        "candidate_states": round_.candidate_states,
        "created_at": round_.created_at.isoformat(),
    }


def comparison_results(instance: RagInstance, round_: ComparisonRound) -> list[dict]:
    results = []
    for candidate_id in round_.candidate_ids:
        candidate = CANDIDATES.get(candidate_id)
        if not candidate:
            continue
        document = instance.documents.get(candidate.document_id)
        if not document:
            continue
        if candidate.preparation_state != CandidateState.READY:
            state = candidate.preparation_state
            round_.candidate_states[candidate.id] = state
            results.append(
                {
                    "candidate": candidate_payload(candidate),
                    "candidate_state": state,
                    "candidate_state_detail": candidate.preparation_error
                    or "후보 검색 인덱스를 준비하고 있어요.",
                    "answer": "이 후보는 아직 비교할 수 없습니다.",
                    "citations": [],
                    "relevance": 0.0,
                    "grounded": False,
                    "generation": {
                        "mode": "NOT_ATTEMPTED",
                        "provider": None,
                        "fallback": False,
                        "fallback_reason": "CANDIDATE_NOT_READY",
                        "grounding_valid": True,
                        "supplied_segment_ids": [],
                        "sentence_citation_ids": [],
                    },
                    "retrieval_metadata": {
                        "provider": candidate.embedding_provider,
                        "warning": candidate.embedding_warning,
                    },
                    "latency_ms": 0,
                }
            )
            continue
        result = answer_for(
            document,
            round_.question,
            candidate.retrieval_config,
            segments=candidate.segments,
            vectors=candidate.vectors,
            embedding_model=instance.embedding_model,
        )
        state = CandidateState.READY if result["citations"] else CandidateState.NO_EVIDENCE
        round_.candidate_states[candidate.id] = state
        results.append(
            {
                "candidate": candidate_payload(candidate),
                **result,
                "candidate_state": state,
                "candidate_state_detail": (
                    "비교할 근거를 찾았습니다."
                    if state == CandidateState.READY
                    else "현재 질문을 뒷받침하는 근거를 찾지 못했습니다."
                ),
                "latency_ms": 120 + (abs(hash(candidate.id + round_.question)) % 480),
            }
        )
    return results


def round_detail_payload(instance: RagInstance, round_: ComparisonRound) -> dict:
    return {**round_payload(round_), "results": comparison_results(instance, round_)}


@app.post(f"{API_PREFIX}/tuning-rounds/{{round_id}}/vote")
def vote(round_id: str, body: VoteRequest) -> dict:
    round_ = ROUNDS.get(round_id)
    if not round_:
        raise not_found("비교 라운드")
    unexpected = set(body.candidate_ids) - set(round_.candidate_ids)
    if unexpected:
        raise HTTPException(422, detail={"code": "CANDIDATE_NOT_IN_ROUND", "message": "현재 라운드에 없는 후보입니다.", "details": {"candidate_ids": sorted(unexpected)}})
    instance = get_instance(round_.instance_id)
    if not all(candidate_id in round_.candidate_states for candidate_id in round_.candidate_ids):
        comparison_results(instance, round_)
    unavailable = [
        candidate_id
        for candidate_id in body.candidate_ids
        if round_.candidate_states.get(candidate_id) != CandidateState.READY
    ]
    if unavailable:
        raise HTTPException(
            422,
            detail={
                "code": "CANDIDATE_NOT_SELECTABLE",
                "message": "준비되지 않았거나 근거가 없는 후보는 선택할 수 없습니다.",
                "details": {
                    "candidate_ids": unavailable,
                    "states": {candidate_id: round_.candidate_states.get(candidate_id) for candidate_id in unavailable},
                },
            },
        )
    if round_.selected_candidate_ids:
        raise HTTPException(409, detail={"code": "ROUND_ALREADY_VOTED", "message": "이 라운드에는 이미 투표했습니다."})
    round_.selected_candidate_ids = body.candidate_ids
    for candidate_id in body.candidate_ids:
        CANDIDATES[candidate_id].selection_count += 1
    persist_state()
    return {"round": round_payload(round_), "tuning_status": tuning_status(instance, round_.document_ids)}


def tuning_status(instance: RagInstance, document_ids: list[str]) -> dict:
    candidates = [CANDIDATES[candidate_id] for document_id in document_ids for candidate_id in instance.documents[document_id].candidate_ids]
    counts = Counter(candidate.selection_count for candidate in candidates)
    top_count = max(counts) if counts else 0
    leaders = [candidate for candidate in candidates if candidate.selection_count == top_count]
    return {"candidates": [candidate_payload(candidate) for candidate in candidates], "leader_candidate_ids": [candidate.id for candidate in leaders], "can_finalize": top_count > 0 and len(leaders) == 1, "message": "단독 1위 후보가 생기면 확정할 수 있습니다." if len(leaders) != 1 else "단독 1위 후보를 확정할 수 있습니다."}


@app.get(f"{API_PREFIX}/rag-instances/{{instance_id}}/tuning-status")
def get_tuning_status(instance_id: str, document_ids: list[str] = Query(...)) -> dict:
    instance = get_instance(instance_id)
    if any(document_id not in instance.documents for document_id in document_ids):
        raise HTTPException(422, detail={"code": "DOCUMENT_NOT_IN_INSTANCE", "message": "선택한 문서가 이 RAG에 없습니다."})
    return tuning_status(instance, document_ids)


def finalize_retuning_outcomes(instance: RagInstance, document: Document, winner: Candidate) -> None:
    """Close comparable retuning evidence only when its new pipeline is selected."""
    for artifact_id in instance.artifact_ids:
        artifact = ARTIFACTS.get(artifact_id)
        if not artifact or artifact.type != "RETUNING_OUTCOME" or document.id not in artifact.context_document_ids:
            continue
        selected = artifact.metadata.setdefault("selected_pipelines", {})
        if document.id in selected:
            continue
        selected[document.id] = candidate_payload(winner)
        pending = set(artifact.context_document_ids) - set(selected)
        artifact.metadata["selection_state"] = "FINALIZED" if not pending else "PARTIALLY_FINALIZED"
        artifact.metadata["pending_document_ids"] = sorted(pending)
        artifact.metadata["summary"] = "재튜닝 후 선택한 파이프라인을 기준선과 비교할 수 있습니다. 관측값은 모델 품질 보장이 아닙니다."
        artifact.updated_at = datetime.now(UTC)


@app.post(f"{API_PREFIX}/rag-instances/{{instance_id}}/tuning/finalize")
def finalize(instance_id: str, body: FinalizeRequest) -> dict:
    instance = get_instance(instance_id)
    document = instance.documents.get(body.document_id)
    if not document:
        raise not_found("문서")
    status_ = tuning_status(instance, [document.id])
    if not status_["can_finalize"]:
        raise HTTPException(409, detail={"code": "TUNING_TIED_OR_UNVOTED", "message": "동점이거나 투표가 없어 확정할 수 없습니다.", "details": status_})
    winner = CANDIDATES[status_["leader_candidate_ids"][0]]
    for candidate_id in list(document.candidate_ids):
        candidate = CANDIDATES[candidate_id]
        if candidate.id == winner.id:
            candidate.finalized, candidate.is_temporary = True, False
        else:
            del CANDIDATES[candidate.id]
            instance.candidate_ids.remove(candidate.id)
            document.candidate_ids.remove(candidate.id)
    document.finalized_candidate_id = winner.id
    finalize_retuning_outcomes(instance, document, winner)
    instance.status = InstanceStatus.READY if all(item.finalized_candidate_id for item in instance.documents.values()) else InstanceStatus.TUNING
    artifact = register_artifact(
        instance,
        type="PIPELINE_DECISION",
        title=f"{document.filename}의 확정 설정",
        context_document_ids=[document.id],
        metadata={
            "context_status": "AVAILABLE",
            "selection_count": winner.selection_count,
            "pipeline": candidate_payload(winner),
            "comparison": comparison_plan_payload(document),
        },
        payload={"document_id": document.id, "candidate_id": winner.id},
    )
    reindex = schedule_full_reindex(instance, document)
    persist_state()
    return {
        "instance": instance_payload(instance, include_documents=True),
        "finalized_candidate": candidate_payload(winner),
        "artifact": artifact_payload(artifact),
        "full_reindex": (
            {
                **full_reindex_payload(document),
                "job": job_payload(reindex[0]),
                "artifact": artifact_payload(reindex[1]),
            }
            if reindex
            else {**full_reindex_payload(document), "job": None, "artifact": None}
        ),
    }


def selected_documents_preflight(instance_id: str, document_ids: list[str]) -> tuple[RagInstance, list[Document], list[dict], list[dict]]:
    """One validation source for REST, SSE, and read-only search eligibility."""
    instance = get_instance(instance_id)
    documents = []
    statuses = []
    conflicts = []
    for document_id in document_ids:
        document = instance.documents.get(document_id)
        if not document:
            conflict = {
                "document_id": document_id,
                "eligible": False,
                "code": "DOCUMENT_NOT_FOUND",
                "action": "REMOVE_DOCUMENT",
                "message": "이 RAG 인스턴스에서 문서를 찾을 수 없습니다.",
            }
            statuses.append(conflict)
            conflicts.append({**conflict, "http_status": 404})
            continue
        if not document.finalized_candidate_id:
            conflict = {
                "document_id": document.id,
                "filename": document.filename,
                "eligible": False,
                "code": "DOCUMENT_NOT_FINALIZED",
                "action": "TUNE_DOCUMENT",
                "message": "튜닝을 마친 문서만 실사용 검색에 포함할 수 있습니다.",
                "full_reindex": full_reindex_payload(document),
            }
            statuses.append(conflict)
            conflicts.append({**conflict, "http_status": 409})
            continue
        reindex = full_reindex_payload(document)
        if not reindex["search_eligible"]:
            state = document.full_reindex_state
            failed = state in {JobState.FAILED, JobState.CANCELLED}
            conflict = {
                "document_id": document.id,
                "filename": document.filename,
                "eligible": False,
                "code": "FULL_REINDEX_FAILED" if failed else "FULL_REINDEX_PENDING",
                "action": "RETRY_FULL_REINDEX" if failed else "WAIT_FOR_FULL_REINDEX",
                "message": (
                    "전체 문서 재인덱싱이 완료되지 않았습니다. 재시도 후 검색할 수 있습니다."
                    if failed
                    else "샘플 비교에서 고른 설정으로 전체 문서를 재인덱싱 중입니다. 완료 후 검색할 수 있습니다."
                ),
                "full_reindex": reindex,
            }
            statuses.append(conflict)
            conflicts.append({**conflict, "http_status": 409})
            continue
        documents.append(document)
        statuses.append({
            "document_id": document.id,
            "filename": document.filename,
            "eligible": True,
            "code": None,
            "action": None,
            "full_reindex": reindex,
        })
    return instance, documents, statuses, conflicts


def search_documents(instance_id: str, document_ids: list[str]) -> tuple[RagInstance, list[Document]]:
    """Keep established REST/SSE validation errors while sharing preflight facts."""
    instance, documents, _, conflicts = selected_documents_preflight(instance_id, document_ids)
    if not conflicts:
        return instance, documents
    conflict = conflicts[0]
    if conflict["code"] == "DOCUMENT_NOT_FOUND":
        raise not_found("문서")
    if conflict["code"] == "DOCUMENT_NOT_FINALIZED":
        raise HTTPException(409, detail={"code": conflict["code"], "message": conflict["message"]})
    raise HTTPException(
        409,
        detail={"code": conflict["code"], "message": conflict["message"], "details": conflict["full_reindex"]},
    )


@app.get(f"{API_PREFIX}/rag-instances/{{instance_id}}/search/preflight")
def search_preflight(instance_id: str, document_ids: list[str] = Query(...)) -> dict:
    """Read-only eligibility report; it does not retrieve, generate, or persist."""
    instance, documents, statuses, conflicts = selected_documents_preflight(instance_id, document_ids)
    return {
        "instance_id": instance.id,
        "eligible": not conflicts,
        "document_count": len(document_ids),
        "eligible_document_ids": [document.id for document in documents],
        "documents": statuses,
        "conflicts": conflicts,
        "next_actions": sorted({conflict["action"] for conflict in conflicts}),
    }


@app.post(f"{API_PREFIX}/rag-instances/{{instance_id}}/search")
def search(instance_id: str, body: SearchRequest) -> dict:
    instance, documents = search_documents(instance_id, body.document_ids)
    if len(documents) == 1:
        # Keep the established single-document retrieval and answer contract intact.
        document = documents[0]
        candidate = CANDIDATES[document.finalized_candidate_id]
        retrieval = body.retrieval_config or candidate.retrieval_config
        answer = answer_for(
            document,
            body.question,
            retrieval,
            body.sensitivity,
            segments=candidate.segments,
            vectors=candidate.vectors,
            embedding_model=instance.embedding_model,
        )
        answer["grouped_citations"] = grouped_citations(answer["citations"], documents)
    else:
        retrieval = body.retrieval_config or "per_document"
        answer = answer_for_documents(
            documents,
            body.question,
            body.sensitivity,
            instance.embedding_model,
            body.retrieval_config,
        )
    citations = [{**citation, "number": index} for index, citation in enumerate(answer["citations"], start=1)]
    grouped = grouped_citations(citations, documents)
    artifact = register_artifact(
        instance,
        type="ANSWER",
        title=f"검색 답변 · {body.question[:48]}",
        context_document_ids=body.document_ids,
        metadata={
            "context_status": "AVAILABLE",
            "grounded": answer["grounded"],
            "relevance": answer["relevance"],
            "retrieval_config": retrieval,
            "sensitivity": body.sensitivity,
            "retrieval_metadata": answer.get("retrieval_metadata", {}),
            "generation": answer.get("generation", {}),
        },
        payload={
            "question": body.question,
            "answer": answer["answer"],
            "citations": citations,
            "grouped_citations": grouped,
            "retrieval_metadata": answer.get("retrieval_metadata", {}),
            "generation": answer.get("generation", {}),
        },
    )
    persist_state()
    return {
        "question": body.question,
        "retrieval_config": retrieval,
        "sensitivity": body.sensitivity,
        "answer": answer["answer"],
        "citations": citations,
        "grouped_citations": grouped,
        "grounded": answer["grounded"],
        "relevance": answer["relevance"],
        "retrieval_metadata": answer.get("retrieval_metadata", {}),
        "generation": answer.get("generation", {}),
        "artifact": artifact_payload(artifact),
    }


@app.get(f"{API_PREFIX}/rag-instances/{{instance_id}}/search/stream")
async def search_stream(
    instance_id: str,
    request: Request,
    question: str,
    document_ids: list[str] = Query(...),
    sensitivity: Sensitivity = Sensitivity.BALANCED,
) -> StreamingResponse:
    # Preflight before opening an SSE 200 response, so full-reindex errors keep
    # the identical structured HTTP 409 contract as POST /search.
    search_documents(instance_id, document_ids)

    async def events() -> AsyncIterator[str]:
        yield f"event: status\ndata: {json.dumps({'phase': 'RETRIEVING', 'cancellable': True, 'streaming': 'BUFFERED_REPLAY'})}\n\n"
        if await request.is_disconnected():
            return
        # The generator HTTP contract is request/response, not token streaming.
        # Run it off the event loop so the first status reaches the client before
        # retrieval/generation finish; only safe, validated answer tokens replay.
        result = await run_in_threadpool(
            search,
            instance_id,
            SearchRequest(question=question, document_ids=document_ids, sensitivity=sensitivity),
        )
        if await request.is_disconnected():
            return
        yield f"event: status\ndata: {json.dumps({'phase': 'ANSWER_READY', 'cancellable': True, 'streaming': 'BUFFERED_REPLAY'})}\n\n"
        yield f"event: citations\ndata: {json.dumps(result['citations'], ensure_ascii=False)}\n\n"
        for index, token in enumerate(result["answer"].split(" ")):
            if await request.is_disconnected():
                return
            yield f"event: token\ndata: {json.dumps({'token': token + ' ', 'index': index, 'delivery': 'BUFFERED_REPLAY'}, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {json.dumps({'grounded': result['grounded'], 'relevance': result['relevance'], 'grouped_citations': result.get('grouped_citations', []), 'retrieval_metadata': result.get('retrieval_metadata', {}), 'generation': result.get('generation', {}), 'artifact_id': result.get('artifact', {}).get('id'), 'streaming': {'mode': 'BUFFERED_REPLAY', 'server_cancellation': 'disconnect_stops_future_events_but_does_not_interrupt_active_provider_request'}})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def find_document(document_id: str) -> tuple[RagInstance, Document] | None:
    for instance in INSTANCES.values():
        document = instance.documents.get(document_id)
        if document:
            return instance, document
    return None


def segment_collection_for(document: Document, segment_id: str) -> list[Segment] | None:
    if any(segment.id == segment_id for segment in document.segments):
        return document.segments
    for candidate in CANDIDATES.values():
        if candidate.document_id == document.id and any(segment.id == segment_id for segment in candidate.segments):
            return candidate.segments
    return None


def segment_viewer_payload(instance: RagInstance, document: Document, segment: Segment, collection: list[Segment]) -> dict:
    current_index = collection.index(segment)
    return {
        "citation": citation_payload(document, segment, 1),
        "viewer": {
            "document_id": document.id,
            "filename": document.filename,
            "content_type": document.content_type,
            "content": document.content,
            "highlight": {"segment_id": segment.id, "start_offset": segment.start_offset, "end_offset": segment.end_offset, "ordinal": segment.ordinal},
            "previous_segment_id": collection[current_index - 1].id if current_index else None,
            "next_segment_id": collection[current_index + 1].id if current_index + 1 < len(collection) else None,
        },
        "context": {"rag_instance_id": instance.id, "rag_instance_name": instance.name},
    }


@app.get(f"{API_PREFIX}/documents/{{document_id}}/segments/{{segment_id}}")
def navigate_to_segment(document_id: str, segment_id: str) -> dict:
    found = find_document(document_id)
    if not found:
        raise not_found("문서")
    instance, document = found
    collection = segment_collection_for(document, segment_id)
    segment = next((item for item in collection or [] if item.id == segment_id), None)
    if not segment:
        raise not_found("근거 조각")
    return segment_viewer_payload(instance, document, segment, collection or [])


@app.get(f"{API_PREFIX}/rag-instances/{{instance_id}}/artifacts")
def list_artifacts(instance_id: str) -> dict:
    instance = get_instance(instance_id)
    artifacts = [ARTIFACTS[artifact_id] for artifact_id in instance.artifact_ids if artifact_id in ARTIFACTS]
    return {"items": [artifact_payload(artifact) for artifact in sorted(artifacts, key=lambda artifact: artifact.updated_at, reverse=True)], "total": len(artifacts)}


@app.get(f"{API_PREFIX}/rag-instances/{{instance_id}}/artifacts/{{artifact_id}}")
def get_artifact(instance_id: str, artifact_id: str) -> dict:
    instance = get_instance(instance_id)
    artifact = ARTIFACTS.get(artifact_id)
    if not artifact or artifact.id not in instance.artifact_ids:
        raise not_found("결과물")
    return artifact_payload(artifact, include_payload=True)


@app.delete(f"{API_PREFIX}/rag-instances/{{instance_id}}/artifacts/{{artifact_id}}", status_code=status.HTTP_200_OK)
def delete_artifact(instance_id: str, artifact_id: str) -> dict:
    instance = get_instance(instance_id)
    artifact = ARTIFACTS.get(artifact_id)
    if not artifact or artifact_id not in instance.artifact_ids:
        raise not_found("결과물")
    del ARTIFACTS[artifact_id]
    instance.artifact_ids.remove(artifact_id)
    persist_state()
    return {"deleted_artifact_id": artifact_id, "artifact_count": len(instance.artifact_ids)}


@app.post(f"{API_PREFIX}/rag-instances/{{instance_id}}/feedback", status_code=status.HTTP_201_CREATED)
def feedback(instance_id: str, body: FeedbackRequest) -> dict:
    instance = get_instance(instance_id)
    if body.artifact_id and body.artifact_id not in instance.artifact_ids:
        raise HTTPException(422, detail={"code": "ARTIFACT_NOT_IN_INSTANCE", "message": "이 RAG에 속하지 않는 결과물입니다."})
    invalid_documents = set(body.document_ids) - set(instance.documents)
    if invalid_documents:
        raise HTTPException(422, detail={"code": "DOCUMENT_NOT_IN_INSTANCE", "message": "선택한 문서가 이 RAG에 없습니다.", "details": {"document_ids": sorted(invalid_documents)}})
    item = {"id": new_id(), "instance_id": instance_id, "rating": body.rating, "comment": body.comment, "artifact_id": body.artifact_id, "document_ids": body.document_ids, "citation_ids": body.citation_ids, "category": body.category, "created_at": now()}
    FEEDBACK.append(item)
    signal = feedback_signal(instance)
    persist_state()
    return {"feedback": item, "retuning_signal": signal, "retuning_recommended": signal["recommended"]}


@app.get(f"{API_PREFIX}/rag-instances/{{instance_id}}/feedback-summary")
def feedback_summary(instance_id: str) -> dict:
    instance = get_instance(instance_id)
    items = [item for item in FEEDBACK if item["instance_id"] == instance_id]
    signal = feedback_signal(instance)
    return {
        "positive_count": sum(1 for item in items if item["rating"] > 0),
        "negative_count": sum(1 for item in items if item["rating"] < 0),
        "total": len(items),
        "retuning_signal": signal,
        "retuning_recommendation": signal,
    }


@app.get(f"{API_PREFIX}/rag-instances/{{instance_id}}/retuning-recommendation")
def get_retuning_recommendation(instance_id: str) -> dict:
    """Expose every recommendation input instead of hiding a numeric trigger."""
    instance = get_instance(instance_id)
    signal = feedback_signal(instance)
    baseline_document_ids = [
        document_id
        for document_id in signal["eligible_document_ids"]
        if instance.documents[document_id].finalized_candidate_id
    ]
    return {
        **signal,
        "baseline_snapshot": (
            retuning_baseline_snapshot(instance, baseline_document_ids)
            if baseline_document_ids
            else {
                "version": RETUNING_SIGNAL_VERSION,
                "captured_at": now(),
                "document_ids": [],
                "selected_pipelines": [],
                "recommendation": signal,
            }
        ),
    }


@app.post(f"{API_PREFIX}/rag-instances/{{instance_id}}/retune", status_code=status.HTTP_202_ACCEPTED)
def retune_documents(instance_id: str, body: RetuneRequest) -> dict:
    instance = get_instance(instance_id)
    documents = []
    for document_id in body.document_ids:
        document = instance.documents.get(document_id)
        if not document:
            raise not_found("문서")
        if not document.finalized_candidate_id:
            raise HTTPException(409, detail={"code": "DOCUMENT_ALREADY_TUNING", "message": "이미 튜닝 중인 문서입니다."})
        documents.append(document)
    baseline = retuning_baseline_snapshot(instance, body.document_ids)
    baseline_artifact = register_artifact(
        instance,
        type="RETUNING_BASELINE",
        title="재튜닝 전 기준선",
        context_document_ids=body.document_ids,
        metadata={
            "context_status": "AVAILABLE",
            "signal_version": RETUNING_SIGNAL_VERSION,
            "summary": "재튜닝 전 확정 파이프라인과 저장된 관측 신호를 고정했습니다.",
            "recommendation": baseline["recommendation"],
        },
        payload=baseline,
    )
    for document in documents:
        for candidate_id in list(document.candidate_ids):
            CANDIDATES.pop(candidate_id, None)
            if candidate_id in instance.candidate_ids:
                instance.candidate_ids.remove(candidate_id)
        document.candidate_ids = []
        document.finalized_candidate_id = None
        document.pipeline_mode = PipelineMode.RETUNE
        document.full_reindex_job_id = None
        document.full_reindex_state = None
        document.parse_status = "UPLOADED"
        document.segments = []
    instance.status = InstanceStatus.SETTING_UP
    artifact = register_artifact(
        instance,
        type="RETUNING_RUN",
        title="재튜닝 준비 작업",
        context_document_ids=body.document_ids,
        metadata={
            "context_status": "AVAILABLE",
            "reason": body.reason,
            "summary": "새 비교 후보를 준비하고 있어요.",
            "baseline_artifact_id": baseline_artifact.id,
            "signal_version": RETUNING_SIGNAL_VERSION,
        },
        artifact_status=ArtifactStatus.PROCESSING,
    )
    job = ProcessingJob(
        id=new_id(),
        instance_id=instance.id,
        document_ids=body.document_ids,
        state=JobState.QUEUED,
        current_step="재튜닝 준비를 시작할 예정이에요.",
        completed_units=0,
        total_units=3,
        created_at=datetime.now(UTC),
        stages=job_stages(PipelineMode.RETUNE),
        artifact_id=artifact.id,
        pipeline_mode=PipelineMode.RETUNE,
    )
    JOBS[job.id] = job
    for document in documents:
        document.processing_job_id = job.id
    persist_state()
    start_processing_job(job, PipelineMode.RETUNE)
    return {
        "job": job_payload(job),
        "artifact": artifact_payload(artifact),
        "baseline_artifact": artifact_payload(baseline_artifact),
        "recommendation": baseline["recommendation"],
        "documents": [document_payload(document) for document in documents],
        "next_action": "TUNE_DOCUMENT",
    }


@app.delete(f"{API_PREFIX}/rag-instances/{{instance_id}}/documents/{{document_id}}", status_code=status.HTTP_200_OK)
def delete_document(instance_id: str, document_id: str) -> dict:
    instance = get_instance(instance_id)
    document = instance.documents.pop(document_id, None)
    if not document:
        raise not_found("문서")
    for candidate_id in document.candidate_ids:
        CANDIDATES.pop(candidate_id, None)
        if candidate_id in instance.candidate_ids:
            instance.candidate_ids.remove(candidate_id)
    for artifact_id in instance.artifact_ids:
        artifact = ARTIFACTS.get(artifact_id)
        if artifact and document_id in artifact.context_document_ids:
            deleted_document_ids = artifact.metadata.setdefault("deleted_document_ids", [])
            if document_id not in deleted_document_ids:
                deleted_document_ids.append(document_id)
            artifact.metadata["context_status"] = "PARTIAL" if len(artifact.context_document_ids) > 1 else "UNAVAILABLE"
            artifact.updated_at = datetime.now(UTC)
    instance.status = InstanceStatus.SETTING_UP if not instance.documents else (InstanceStatus.READY if all(item.finalized_candidate_id for item in instance.documents.values()) else InstanceStatus.TUNING)
    persist_state()
    return {"deleted_document": {"id": document.id, "filename": document.filename}, "instance_status": instance.status, "artifacts_with_unavailable_context": [artifact_id for artifact_id in instance.artifact_ids if ARTIFACTS.get(artifact_id) and document_id in ARTIFACTS[artifact_id].metadata.get("deleted_document_ids", [])]}
