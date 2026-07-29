"""FastAPI contract for the local, functional RAG Portal MVP.

The first production-shaped slice uses deterministic local parsing and lexical
retrieval. Candidate pipelines produce their own persisted chunks, so tuning
compares a real difference in retrieval context before a provider-backed
embedding/vector layer is introduced.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import json
import os
import re
from threading import RLock, Thread
from typing import Annotated, AsyncIterator
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.state_store import StateStore


API_PREFIX = "/api/v1"
STATE_STORE = StateStore(os.getenv("RAG_PORTAL_DB_PATH", ".rag-portal.sqlite3"))
STATE_LOCK = RLock()


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


class Sensitivity(StrEnum):
    FLEXIBLE = "flexible"
    BALANCED = "balanced"
    STRICT = "strict"


class PipelineMode(StrEnum):
    """How a newly added source gets its retrieval pipeline."""

    REUSE = "reuse"
    RETUNE = "retune"


class ArtifactStatus(StrEnum):
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class Questionnaire(BaseModel):
    primary_language: str = "ko"
    requires_on_premise: bool = False
    budget: str = "standard"
    multi_hop_questions: bool = False


class InstanceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    questionnaire: Questionnaire = Field(default_factory=Questionnaire)


class DocumentInput(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
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
    profile: str = "short"
    parse_status: str = "PARSED"
    processing_job_id: str | None = None
    pipeline_mode: PipelineMode = PipelineMode.RETUNE
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


@dataclass
class ComparisonRound:
    id: str
    instance_id: str
    document_ids: list[str]
    question: str
    candidate_ids: list[str]
    created_at: datetime
    selected_candidate_ids: list[str] = field(default_factory=list)


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
FEEDBACK: list[dict] = []
ARTIFACTS: dict[str, Artifact] = {}


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
                        "parse_status": document.parse_status,
                        "processing_job_id": document.processing_job_id,
                        "pipeline_mode": document.pipeline_mode,
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
            }
            for round_ in ROUNDS.values()
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
        ARTIFACTS.clear()
        FEEDBACK.clear()
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
                    profile=raw_document.get("profile", "short"),
                    parse_status=raw_document.get("parse_status", "UPLOADED"),
                    processing_job_id=raw_document.get("processing_job_id"),
                    pipeline_mode=PipelineMode(raw_document.get("pipeline_mode", PipelineMode.RETUNE)),
                    created_at=decode_time(raw_document.get("created_at")) or datetime.now(UTC),
                    candidate_ids=raw_document.get("candidate_ids", []),
                    finalized_candidate_id=raw_document.get("finalized_candidate_id"),
                )
                instance.documents[document.id] = document
            INSTANCES[instance.id] = instance
        for item in payload.get("candidates", []):
            CANDIDATES[item["id"]] = Candidate(
                **{**item, "segments": [Segment(**segment) for segment in item.get("segments", [])]}
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


def now() -> str:
    return datetime.now(UTC).isoformat()


def new_id() -> str:
    return str(uuid4())


def not_found(resource: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"{resource}을(를) 찾을 수 없습니다."})


def get_instance(instance_id: str) -> RagInstance:
    instance = INSTANCES.get(instance_id)
    if not instance:
        raise not_found("RAG 인스턴스")
    return instance


def recommend_embedding(questionnaire: Questionnaire) -> str:
    if questionnaire.requires_on_premise:
        return "Qwen3-Embedding-0.6B"
    if questionnaire.primary_language.lower() in {"ko", "korean", "한국어", "multilingual"}:
        return "BGE-M3"
    if questionnaire.budget.lower() in {"low", "free", "낮음"}:
        return "EmbeddingGemma-300M"
    return "BGE-M3"


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


def document_profile(document: Document) -> str:
    lowered = f"{document.filename} {document.content}".lower()
    if document.filename.lower().endswith((".csv", ".xlsx", ".xls")) or "|" in document.content or "," in document.content[:500]:
        return "table"
    if document.filename.lower().endswith(".pdf") and ("scan" in lowered or "이미지" in lowered):
        return "scanned"
    if len(document.content) > 2200 or any(marker in document.content for marker in ("제1", "제2", "chapter", "##")):
        return "structured"
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


def fixed_chunks(document: Document, width: int = 360, overlap: int = 48) -> list[Segment]:
    chunks: list[Segment] = []
    cursor = 0
    content = document.content
    while cursor < len(content):
        end = min(len(content), cursor + width)
        if end < len(content):
            boundary = max(content.rfind("\n", cursor + 120, end), content.rfind(" ", cursor + 120, end))
            if boundary > cursor:
                end = boundary + 1
        chunk = make_chunk(content, cursor, end, len(chunks) + 1)
        if chunk:
            chunks.append(chunk)
        if end >= len(content):
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


def structured_chunks(document: Document) -> list[Segment]:
    markers = list(
        re.finditer(r"(?m)^(?=(?:#{1,6}\s+|제\s*\d+\s*(?:조|장)|chapter\b))", document.content, re.IGNORECASE)
    )
    if len(markers) < 2:
        return grouped_source_chunks(document)
    chunks: list[Segment] = []
    starts = [marker.start() for marker in markers]
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(document.content)
        chunk = make_chunk(document.content, start, end, len(chunks) + 1)
        if chunk:
            chunks.append(chunk)
    return chunks


def table_chunks(document: Document) -> list[Segment]:
    lines = list(re.finditer(r"(?m)^.*\S.*$", document.content))
    if len(lines) < 2:
        return grouped_source_chunks(document)
    chunks: list[Segment] = []
    header = lines[0]
    for start_index in range(1, len(lines), 6):
        rows = lines[start_index : start_index + 6]
        chunk = make_chunk(document.content, header.start(), rows[-1].end(), len(chunks) + 1)
        if chunk:
            chunks.append(chunk)
    return chunks


def chunks_for_strategy(document: Document, strategy: str) -> list[Segment]:
    if strategy == "document":
        chunk = make_chunk(document.content, 0, len(document.content), 1)
        return [chunk] if chunk else []
    if strategy == "fixed":
        return fixed_chunks(document)
    if strategy in {"hierarchical", "ocr_hierarchical"}:
        return structured_chunks(document)
    if strategy == "table":
        return table_chunks(document)
    return grouped_source_chunks(document)


def candidate_blueprints(profile: str) -> list[tuple[str, str, str, str]]:
    variable = "BM25" if profile == "table" else "Dense"
    chunkers = {
        "short": [("문서 단위", "document"), ("주제 단위", "semantic"), ("기본 길이", "fixed")],
        "table": [("표 중심", "table"), ("구조 중심", "hierarchical"), ("기본 길이", "fixed")],
        "structured": [("구조 중심", "hierarchical"), ("의미 중심", "semantic"), ("기본 길이", "fixed")],
        "scanned": [("OCR 구조 중심", "ocr_hierarchical"), ("OCR 의미 중심", "ocr_semantic"), ("기본 길이", "fixed")],
    }[profile]
    retrievals = [("일반 검색", "hybrid"), ("정밀 검색", "hybrid_rerank"), ("용어 검색" if variable == "BM25" else "의미 검색", variable.lower())]
    return [
        (chunk_label, chunk_key, retrieval_label, retrieval_key)
        for chunk_label, chunk_key in chunkers
        for retrieval_label, retrieval_key in retrievals
    ]


def create_candidates(instance: RagInstance, document: Document) -> list[Candidate]:
    candidates = []
    for chunk_label, chunk_key, retrieval_label, retrieval_key in candidate_blueprints(document_profile(document)):
        candidate = Candidate(
            id=new_id(),
            document_id=document.id,
            chunking_strategy=chunk_key,
            retrieval_config=retrieval_key,
            friendly_name=f"{chunk_label} + {retrieval_label}",
            technical_description=f"{chunk_key} chunking with {retrieval_key} retrieval",
            segments=chunks_for_strategy(document, chunk_key),
        )
        CANDIDATES[candidate.id] = candidate
        candidates.append(candidate)
        document.candidate_ids.append(candidate.id)
        instance.candidate_ids.append(candidate.id)
    return candidates


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


def feedback_signal(instance: RagInstance) -> dict:
    negative = [item for item in FEEDBACK if item["instance_id"] == instance.id and item["rating"] < 0]
    threshold = 3
    document_ids = sorted({document_id for item in negative for document_id in item.get("document_ids", []) if document_id in instance.documents})
    if not document_ids:
        document_ids = [document.id for document in instance.documents.values() if document.finalized_candidate_id]
    recommended = len(negative) >= threshold
    return {
        "recommended": recommended,
        "negative_count": len(negative),
        "threshold": threshold,
        "eligible_document_ids": document_ids,
        "message": "부정 피드백이 누적되어 재튜닝을 권장합니다." if recommended else f"부정 피드백 {max(threshold - len(negative), 0)}건이 더 쌓이면 재튜닝을 권장합니다.",
        "action": "START_RETUNE" if recommended else None,
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


def evidence_for(segments: list[Segment], question: str, retrieval: str) -> tuple[Segment | None, float]:
    best: tuple[Segment | None, float] = (None, 0.0)
    for segment in segments:
        segment_score = score(question, segment, retrieval)
        if segment_score > best[1]:
            best = (segment, segment_score)
    return best


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


def answer_for(
    document: Document,
    question: str,
    retrieval: str,
    sensitivity: Sensitivity = Sensitivity.BALANCED,
    segments: list[Segment] | None = None,
) -> dict:
    segment, relevance = evidence_for(segments if segments is not None else document.segments, question, retrieval)
    thresholds = {Sensitivity.FLEXIBLE: 0.05, Sensitivity.BALANCED: 0.12, Sensitivity.STRICT: 0.24}
    if not segment or relevance < thresholds[sensitivity]:
        return {
            "answer": "관련 문서를 찾지 못했습니다. 검색 범위나 질문을 조금 더 구체적으로 바꿔보세요.",
            "citations": [],
            "relevance": round(relevance, 3),
            "grounded": False,
        }
    sentence = segment.text.split(". ")[0].strip()
    if not sentence.endswith((".", "다.", "요.")):
        sentence += "."
    return {
        "answer": f"{sentence} [1]",
        "citations": [citation_payload(document, segment, 1)],
        "relevance": round(relevance, 3),
        "grounded": True,
    }


def candidate_payload(candidate: Candidate) -> dict:
    return {
        "id": candidate.id,
        "document_id": candidate.document_id,
        "chunking_strategy": candidate.chunking_strategy,
        "retrieval_config": candidate.retrieval_config,
        "friendly_name": candidate.friendly_name,
        "technical_description": candidate.technical_description,
        "is_temporary": candidate.is_temporary,
        "selection_count": candidate.selection_count,
        "finalized": candidate.finalized,
        "chunk_count": len(candidate.segments),
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
        "profile": document.profile,
        "parse_status": document.parse_status,
        "processing_job_id": document.processing_job_id,
        "pipeline_mode": document.pipeline_mode,
        "segment_count": len(document.segments),
        "finalized_candidate_id": document.finalized_candidate_id,
        "created_at": document.created_at.isoformat(),
        "candidates": [candidate_payload(CANDIDATES[candidate_id]) for candidate_id in document.candidate_ids],
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


@app.get(f"{API_PREFIX}/rag-instances")
def list_instances() -> dict:
    return {"items": [instance_payload(instance) for instance in sorted(INSTANCES.values(), key=lambda item: item.created_at, reverse=True)], "total": len(INSTANCES)}


@app.post(f"{API_PREFIX}/rag-instances", status_code=status.HTTP_201_CREATED)
def create_instance(body: InstanceCreate) -> dict:
    instance = RagInstance(
        id=new_id(),
        name=body.name,
        status=InstanceStatus.SETTING_UP,
        embedding_model=recommend_embedding(body.questionnaire),
        graphrag_enabled=body.questionnaire.multi_hop_questions,
    )
    INSTANCES[instance.id] = instance
    persist_state()
    return {**instance_payload(instance), "recommendation": {"embedding_model": instance.embedding_model, "reason": "질문 응답을 바탕으로 프로젝트 전체에 고정할 임베딩 모델을 추천했습니다."}}


@app.get(f"{API_PREFIX}/rag-instances/{{instance_id}}")
def get_instance_detail(instance_id: str) -> dict:
    return instance_payload(get_instance(instance_id), include_documents=True)


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


def complete_stage(job: ProcessingJob, key: str, state: JobState, current_step: str, completed: int) -> None:
    job.state = state
    job.current_step = current_step
    job.completed_units = completed
    for stage in job.stages:
        if stage["key"] == key:
            stage["state"] = "SUCCEEDED"
            stage["completed_at"] = now()
            break


def run_processing_job(job_id: str, mode: PipelineMode, reuse_source_document_id: str | None = None) -> None:
    """Execute the local parser/candidate/index preparation outside the request."""
    try:
        with STATE_LOCK:
            job = JOBS[job_id]
            instance = get_instance(job.instance_id)
            job.state = JobState.PARSING
            job.current_step = "문서 구조를 읽고 있어요."
            for document_id in job.document_ids:
                instance.documents[document_id].parse_status = "PARSING"
            persist_state()

        with STATE_LOCK:
            job = JOBS[job_id]
            instance = get_instance(job.instance_id)
            for document_id in job.document_ids:
                document = instance.documents[document_id]
                document.segments = split_segments(document.content)
                document.profile = document_profile(document)
                document.parse_status = "PARSED"
            complete_stage(job, "PARSING", JobState.GENERATING_CANDIDATES, "비교 후보를 준비하고 있어요.", 1)
            persist_state()

        with STATE_LOCK:
            job = JOBS[job_id]
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
                        segments=chunks_for_strategy(document, source.chunking_strategy),
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
            instance = get_instance(job.instance_id)
            complete_stage(job, "INDEXING", JobState.SUCCEEDED, "검색 준비가 완료되었어요.", 3)
            job.completed_at = datetime.now(UTC)
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
            persist_state()
    except Exception as error:  # pragma: no cover - defensive worker boundary
        with STATE_LOCK:
            job = JOBS.get(job_id)
            if job:
                job.state = JobState.FAILED
                job.current_step = "문서 준비를 마치지 못했어요."
                job.error_message = str(error)
                job.completed_at = datetime.now(UTC)
                artifact = ARTIFACTS.get(job.artifact_id) if job.artifact_id else None
                if artifact:
                    artifact.status = ArtifactStatus.FAILED
                    artifact.updated_at = datetime.now(UTC)
                persist_state()


def start_processing_job(job: ProcessingJob, mode: PipelineMode, reuse_source_document_id: str | None = None) -> None:
    Thread(
        target=run_processing_job,
        args=(job.id, mode, reuse_source_document_id),
        daemon=True,
        name=f"rag-job-{job.id[:8]}",
    ).start()


def resume_pending_jobs() -> None:
    for job in list(JOBS.values()):
        if job.state not in {JobState.QUEUED, JobState.PARSING, JobState.GENERATING_CANDIDATES, JobState.INDEXING}:
            continue
        instance = INSTANCES.get(job.instance_id)
        if not instance or not job.document_ids:
            continue
        first_document = instance.documents.get(job.document_ids[0])
        if not first_document:
            continue
        start_processing_job(job, first_document.pipeline_mode)


restore_state()
resume_pending_jobs()


def reuse_source_for(instance: RagInstance, requested_document_id: str | None) -> tuple[Document, Candidate] | None:
    documents = [instance.documents.get(requested_document_id)] if requested_document_id else list(instance.documents.values())
    for document in documents:
        if document and document.finalized_candidate_id:
            return document, CANDIDATES[document.finalized_candidate_id]
    return None


@app.post(f"{API_PREFIX}/rag-instances/{{instance_id}}/documents", status_code=status.HTTP_202_ACCEPTED)
def upload_documents(instance_id: str, body: DocumentsCreate) -> dict:
    instance = get_instance(instance_id)
    mode = resolved_pipeline_mode(body)
    reuse_source = reuse_source_for(instance, body.reuse_from_document_id) if mode == PipelineMode.REUSE else None
    if mode == PipelineMode.REUSE and not reuse_source:
        raise HTTPException(409, detail={"code": "NO_FINALIZED_PIPELINE_TO_REUSE", "message": "재사용할 확정 파이프라인이 없습니다. 이 문서를 따로 튜닝해 주세요."})
    created: list[Document] = []
    for item in body.documents:
        document = Document(
            id=new_id(),
            filename=item.filename,
            content_type=item.content_type,
            content=item.content,
            segments=[],
            parse_status="UPLOADED",
        )
        document.pipeline_mode = mode
        instance.documents[document.id] = document
        created.append(document)
    instance.status = InstanceStatus.SETTING_UP
    artifact = register_artifact(
        instance,
        type="PROCESSING_RUN",
        title="문서 준비 작업",
        context_document_ids=[item.id for item in created],
        metadata={"pipeline_mode": mode, "context_status": "AVAILABLE", "summary": "문서 준비를 시작했어요."},
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
    )
    JOBS[job.id] = job
    for document in created:
        document.processing_job_id = job.id
    decision = {
        "pipeline_mode": mode,
        "next_action": "TUNE_DOCUMENT" if mode == PipelineMode.RETUNE else "SEARCH_READY",
        "reuse_source_document_id": reuse_source[0].id if reuse_source else None,
        "message": "답변 비교를 시작해 이 문서에 맞는 설정을 고르세요." if mode == PipelineMode.RETUNE else "기존에 확정한 설정을 적용했습니다. 바로 검색할 수 있습니다.",
    }
    persist_state()
    start_processing_job(job, mode, reuse_source[0].id if reuse_source else None)
    return {"job": job_payload(job), "artifact": artifact_payload(artifact), "decision": decision, "documents": [document_payload(item) for item in created]}


def job_payload(job: ProcessingJob) -> dict:
    return {"id": job.id, "instance_id": job.instance_id, "document_ids": job.document_ids, "state": job.state, "current_step": job.current_step, "progress": {"completed": job.completed_units, "total": job.total_units}, "stages": job.stages, "artifact_id": job.artifact_id, "can_retry": job.state == JobState.FAILED, "can_cancel": job.state in {JobState.QUEUED, JobState.PARSING, JobState.GENERATING_CANDIDATES, JobState.INDEXING}, "created_at": job.created_at.isoformat(), "completed_at": job.completed_at.isoformat() if job.completed_at else None, "error_message": job.error_message}


@app.get(f"{API_PREFIX}/rag-jobs/{{job_id}}")
def get_job(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if not job:
        raise not_found("작업")
    return job_payload(job)


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


@app.post(f"{API_PREFIX}/rag-instances/{{instance_id}}/tuning/compare")
def compare_candidates(instance_id: str, body: CompareRequest) -> dict:
    instance = get_instance(instance_id)
    missing = [document_id for document_id in body.document_ids if document_id not in instance.documents]
    if missing:
        raise HTTPException(422, detail={"code": "DOCUMENT_NOT_IN_INSTANCE", "message": "선택한 문서가 이 RAG에 없습니다.", "details": {"document_ids": missing}})
    candidate_ids = [candidate_id for document_id in body.document_ids for candidate_id in instance.documents[document_id].candidate_ids if not CANDIDATES[candidate_id].finalized or True]
    round_ = ComparisonRound(id=new_id(), instance_id=instance.id, document_ids=body.document_ids, question=body.question, candidate_ids=candidate_ids, created_at=datetime.now(UTC))
    ROUNDS[round_.id] = round_
    results = comparison_results(instance, round_)
    artifact = register_artifact(
        instance,
        type="TUNING_COMPARISON",
        title=f"비교 라운드 · {body.question[:48]}",
        context_document_ids=body.document_ids,
        metadata={"round_id": round_.id, "candidate_count": len(candidate_ids), "context_status": "AVAILABLE", "view": "answer_with_inline_citations"},
        payload={"question": body.question, "candidate_ids": candidate_ids},
    )
    persist_state()
    return {"round": round_payload(round_), "artifact": artifact_payload(artifact), "results": results, "view": {"default": "answer_with_inline_citations", "alternate": "source_chunks"}}


def round_payload(round_: ComparisonRound) -> dict:
    return {"id": round_.id, "instance_id": round_.instance_id, "document_ids": round_.document_ids, "question": round_.question, "candidate_ids": round_.candidate_ids, "selected_candidate_ids": round_.selected_candidate_ids, "created_at": round_.created_at.isoformat()}


def comparison_results(instance: RagInstance, round_: ComparisonRound) -> list[dict]:
    results = []
    for candidate_id in round_.candidate_ids:
        candidate = CANDIDATES.get(candidate_id)
        if not candidate:
            continue
        document = instance.documents.get(candidate.document_id)
        if not document:
            continue
        result = answer_for(
            document,
            round_.question,
            candidate.retrieval_config,
            segments=candidate.segments,
        )
        results.append(
            {
                "candidate": candidate_payload(candidate),
                **result,
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
    if round_.selected_candidate_ids:
        raise HTTPException(409, detail={"code": "ROUND_ALREADY_VOTED", "message": "이 라운드에는 이미 투표했습니다."})
    round_.selected_candidate_ids = body.candidate_ids
    for candidate_id in body.candidate_ids:
        CANDIDATES[candidate_id].selection_count += 1
    instance = get_instance(round_.instance_id)
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
    instance.status = InstanceStatus.READY if all(item.finalized_candidate_id for item in instance.documents.values()) else InstanceStatus.TUNING
    artifact = register_artifact(
        instance,
        type="PIPELINE_DECISION",
        title=f"{document.filename}의 확정 설정",
        context_document_ids=[document.id],
        metadata={"context_status": "AVAILABLE", "selection_count": winner.selection_count, "pipeline": candidate_payload(winner)},
        payload={"document_id": document.id, "candidate_id": winner.id},
    )
    persist_state()
    return {"instance": instance_payload(instance, include_documents=True), "finalized_candidate": candidate_payload(winner), "artifact": artifact_payload(artifact)}


@app.post(f"{API_PREFIX}/rag-instances/{{instance_id}}/search")
def search(instance_id: str, body: SearchRequest) -> dict:
    instance = get_instance(instance_id)
    documents = []
    for document_id in body.document_ids:
        document = instance.documents.get(document_id)
        if not document:
            raise not_found("문서")
        if not document.finalized_candidate_id:
            raise HTTPException(409, detail={"code": "DOCUMENT_NOT_FINALIZED", "message": "튜닝을 마친 문서만 실사용 검색에 포함할 수 있습니다."})
        documents.append(document)
    configs = {CANDIDATES[document.finalized_candidate_id].retrieval_config for document in documents}
    retrieval = body.retrieval_config or (next(iter(configs)) if len(configs) == 1 else "hybrid")
    answers = [
        answer_for(
            document,
            body.question,
            retrieval,
            body.sensitivity,
            segments=CANDIDATES[document.finalized_candidate_id].segments,
        )
        for document in documents
    ]
    grounded = [item for item in answers if item["grounded"]]
    if not grounded:
        answer = {"answer": "관련 문서를 찾지 못했습니다. 검색 범위나 질문을 조금 더 구체적으로 바꿔보세요.", "citations": [], "grounded": False, "relevance": 0.0}
    else:
        best = max(grounded, key=lambda item: item["relevance"])
        answer = {**best, "citations": [citation for item in grounded for citation in item["citations"]][:4]}
    citations = [{**citation, "number": index} for index, citation in enumerate(answer["citations"], start=1)]
    artifact = register_artifact(
        instance,
        type="ANSWER",
        title=f"검색 답변 · {body.question[:48]}",
        context_document_ids=body.document_ids,
        metadata={"context_status": "AVAILABLE", "grounded": answer["grounded"], "relevance": answer["relevance"], "retrieval_config": retrieval, "sensitivity": body.sensitivity},
        payload={"question": body.question, "answer": answer["answer"], "citations": citations},
    )
    persist_state()
    return {"question": body.question, "retrieval_config": retrieval, "sensitivity": body.sensitivity, "answer": answer["answer"], "citations": citations, "grounded": answer["grounded"], "relevance": answer["relevance"], "artifact": artifact_payload(artifact)}


@app.get(f"{API_PREFIX}/rag-instances/{{instance_id}}/search/stream")
async def search_stream(instance_id: str, question: str, document_ids: list[str] = Query(...), sensitivity: Sensitivity = Sensitivity.BALANCED) -> StreamingResponse:
    result = search(instance_id, SearchRequest(question=question, document_ids=document_ids, sensitivity=sensitivity))

    async def events() -> AsyncIterator[str]:
        yield f"event: citations\ndata: {json.dumps(result['citations'], ensure_ascii=False)}\n\n"
        for token in result["answer"].split(" "):
            yield f"event: token\ndata: {json.dumps({'token': token + ' '}, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {json.dumps({'grounded': result['grounded'], 'relevance': result['relevance']})}\n\n"

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
    return {"positive_count": sum(1 for item in items if item["rating"] > 0), "negative_count": sum(1 for item in items if item["rating"] < 0), "total": len(items), "retuning_signal": feedback_signal(instance)}


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
        for candidate_id in list(document.candidate_ids):
            CANDIDATES.pop(candidate_id, None)
            if candidate_id in instance.candidate_ids:
                instance.candidate_ids.remove(candidate_id)
        document.candidate_ids = []
        document.finalized_candidate_id = None
        document.pipeline_mode = PipelineMode.RETUNE
        document.parse_status = "UPLOADED"
        document.segments = []
        documents.append(document)
    instance.status = InstanceStatus.SETTING_UP
    artifact = register_artifact(
        instance,
        type="RETUNING_RUN",
        title="재튜닝 준비 작업",
        context_document_ids=body.document_ids,
        metadata={"context_status": "AVAILABLE", "reason": body.reason, "summary": "새 비교 후보를 준비하고 있어요."},
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
    )
    JOBS[job.id] = job
    for document in documents:
        document.processing_job_id = job.id
    persist_state()
    start_processing_job(job, PipelineMode.RETUNE)
    return {"job": job_payload(job), "artifact": artifact_payload(artifact), "documents": [document_payload(document) for document in documents], "next_action": "TUNE_DOCUMENT"}


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
