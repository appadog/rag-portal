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
from threading import RLock
from typing import Annotated, AsyncIterator
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.state_store import StateStore
from app.document_parser import extract_document
from app.job_queue import backend_name, dispatch
from app.model_runtime import execution_plan, runtime_catalog
from app.retrieval import rank as rank_segments
from app.retrieval import embed


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
    CANCELLED = "CANCELLED"


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
    parser: str | None = None
    used_ocr: bool = False
    profile: str = "short"
    chunking_analysis: dict = field(default_factory=dict)
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
    vectors: dict[str, list[float]] = field(default_factory=dict)
    embedding_provider: str | None = None
    embedding_dimension: int = 0
    embedding_warning: str | None = None
    chunking_parameters: dict = field(default_factory=dict)
    selection_reason: str = ""


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
                        "raw_content_base64": document.raw_content_base64,
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
                    raw_content_base64=raw_document.get("raw_content_base64"),
                    profile=raw_document.get("profile", "short"),
                    chunking_analysis=raw_document.get("chunking_analysis", {}),
                    parse_status=raw_document.get("parse_status", "UPLOADED"),
                    parser=raw_document.get("parser"),
                    used_ocr=raw_document.get("used_ocr", False),
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
                **{
                    **item,
                    "segments": [Segment(**segment) for segment in item.get("segments", [])],
                    "vectors": item.get("vectors", {}),
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


def create_candidates(instance: RagInstance, document: Document) -> list[Candidate]:
    candidates = []
    for chunker, retrieval_label, retrieval_key in candidate_blueprints(document):
        candidate = Candidate(
            id=new_id(),
            document_id=document.id,
            chunking_strategy=chunker.strategy,
            retrieval_config=retrieval_key,
            friendly_name=f"{chunker.label} + {retrieval_label}",
            technical_description=f"{chunker.reason} · {chunker.strategy} + {retrieval_key}",
            chunking_parameters=chunker.parameters,
            selection_reason=chunker.reason,
            segments=chunks_for_strategy(document, chunker.strategy, chunker.parameters),
        )
        CANDIDATES[candidate.id] = candidate
        candidates.append(candidate)
        document.candidate_ids.append(candidate.id)
        instance.candidate_ids.append(candidate.id)
    return candidates


def prepare_candidate_index(instance: RagInstance, candidate: Candidate) -> None:
    batch = embed([segment.text for segment in candidate.segments], instance.embedding_model)
    candidate.vectors = {
        segment.id: vector for segment, vector in zip(candidate.segments, batch.vectors)
    }
    candidate.embedding_provider = batch.provider
    candidate.embedding_dimension = batch.dimension
    candidate.embedding_warning = batch.warning


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
        }
    sentence = segment.text.split(". ")[0].strip()
    if not sentence.endswith((".", "다.", "요.")):
        sentence += "."
    return {
        "answer": f"{sentence} [1]",
        "citations": [citation_payload(document, segment, 1)],
        "relevance": round(relevance, 3),
        "grounded": True,
        "retrieval_metadata": retrieval_metadata,
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
        "index": {
            "vector_count": len(candidate.vectors),
            "embedding_provider": candidate.embedding_provider,
            "embedding_dimension": candidate.embedding_dimension,
            "warning": candidate.embedding_warning,
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
        "profile": document.profile,
        "chunking_analysis": document.chunking_analysis,
        "parse_status": document.parse_status,
        "parser": document.parser,
        "used_ocr": document.used_ocr,
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
    if job.cancel_requested:
        raise JobCancelled()


def run_processing_job(job_id: str, mode: PipelineMode, reuse_source_document_id: str | None = None) -> None:
    """Execute the local parser/candidate/index preparation outside the request."""
    try:
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
                parsed = extract_document(
                    filename=document.filename,
                    content_type=document.content_type,
                    content=document.content,
                    content_base64=document.raw_content_base64,
                )
                document.content = parsed.text
                document.parser = parsed.parser
                document.used_ocr = parsed.used_ocr
                document.segments = split_segments(parsed.text)
                document.chunking_analysis = analyze_document_for_chunking(document)
                document.profile = document_profile(document, document.chunking_analysis)
                document.parse_status = "PARSED"
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
            for document_id in job.document_ids:
                document = instance.documents[document_id]
                for candidate_id in document.candidate_ids:
                    prepare_candidate_index(instance, CANDIDATES[candidate_id])
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
    except JobCancelled:
        with STATE_LOCK:
            job = JOBS.get(job_id)
            if job:
                job.state = JobState.CANCELLED
                job.current_step = "문서 준비를 중단했어요."
                job.completed_at = datetime.now(UTC)
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
    job.pipeline_mode = mode
    job.reuse_source_document_id = reuse_source_document_id
    dispatch(
        job.id,
        lambda: run_processing_job(job.id, job.pipeline_mode, job.reuse_source_document_id),
    )


def resume_pending_jobs() -> None:
    for job in list(JOBS.values()):
        if job.state not in {JobState.QUEUED, JobState.PARSING, JobState.GENERATING_CANDIDATES, JobState.INDEXING}:
            continue
        instance = INSTANCES.get(job.instance_id)
        if not instance or not job.document_ids:
            continue
        if not instance.documents.get(job.document_ids[0]):
            continue
        start_processing_job(job, job.pipeline_mode, job.reuse_source_document_id)


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
        pipeline_mode=mode,
        reuse_source_document_id=reuse_source[0].id if reuse_source else None,
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
    return {"id": job.id, "instance_id": job.instance_id, "document_ids": job.document_ids, "state": job.state, "current_step": job.current_step, "progress": {"completed": job.completed_units, "total": job.total_units}, "stages": job.stages, "artifact_id": job.artifact_id, "can_retry": job.state in {JobState.FAILED, JobState.CANCELLED}, "can_cancel": job.state in {JobState.QUEUED, JobState.PARSING, JobState.GENERATING_CANDIDATES, JobState.INDEXING}, "attempt": job.attempt, "queue_backend": backend_name(), "created_at": job.created_at.isoformat(), "completed_at": job.completed_at.isoformat() if job.completed_at else None, "error_message": job.error_message}


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
    if job.state not in {JobState.FAILED, JobState.CANCELLED}:
        raise HTTPException(409, detail={"code": "JOB_NOT_RETRYABLE", "message": "실패하거나 중단된 작업만 다시 시도할 수 있습니다."})
    instance = get_instance(job.instance_id)
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
    job.stages = job_stages(job.pipeline_mode)
    persist_state()
    start_processing_job(job, job.pipeline_mode, job.reuse_source_document_id)
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
            vectors=candidate.vectors,
            embedding_model=instance.embedding_model,
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
            vectors=CANDIDATES[document.finalized_candidate_id].vectors,
            embedding_model=instance.embedding_model,
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
    return {"question": body.question, "retrieval_config": retrieval, "sensitivity": body.sensitivity, "answer": answer["answer"], "citations": citations, "grounded": answer["grounded"], "relevance": answer["relevance"], "retrieval_metadata": answer.get("retrieval_metadata", {}), "artifact": artifact_payload(artifact)}


@app.get(f"{API_PREFIX}/rag-instances/{{instance_id}}/search/stream")
async def search_stream(instance_id: str, question: str, document_ids: list[str] = Query(...), sensitivity: Sensitivity = Sensitivity.BALANCED) -> StreamingResponse:
    result = search(instance_id, SearchRequest(question=question, document_ids=document_ids, sensitivity=sensitivity))

    async def events() -> AsyncIterator[str]:
        yield f"event: citations\ndata: {json.dumps(result['citations'], ensure_ascii=False)}\n\n"
        for token in result["answer"].split(" "):
            yield f"event: token\ndata: {json.dumps({'token': token + ' '}, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {json.dumps({'grounded': result['grounded'], 'relevance': result['relevance'], 'retrieval_metadata': result.get('retrieval_metadata', {}), 'artifact_id': result.get('artifact', {}).get('id')})}\n\n"

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
        pipeline_mode=PipelineMode.RETUNE,
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
