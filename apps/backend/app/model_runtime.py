"""Explicit model-service contract for every RAG pipeline technique."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
import shutil
from typing import Iterable

import httpx


@dataclass(frozen=True)
class ModelService:
    key: str
    technique: str
    model_id: str
    runtime: str
    endpoint_env: str | None
    used_by: tuple[str, ...]
    description: str


MODEL_SERVICES = (
    ModelService(
        key="embedding-bge-m3",
        technique="embedding",
        model_id="BAAI/bge-m3",
        runtime="tei",
        endpoint_env="RAG_EMBEDDING_URL_BGE_M3",
        used_by=("indexing", "dense", "hybrid", "hybrid_rerank"),
        description="한국어·영어 혼합 문서의 기본 다국어 임베딩 모델",
    ),
    ModelService(
        key="embedding-qwen3-0-6b",
        technique="embedding",
        model_id="Qwen/Qwen3-Embedding-0.6B",
        runtime="tei",
        endpoint_env="RAG_EMBEDDING_URL_QWEN3_EMBEDDING_0_6B",
        used_by=("indexing", "dense", "hybrid", "hybrid_rerank"),
        description="자체 운영에 적합한 경량 임베딩 모델",
    ),
    ModelService(
        key="embedding-gemma-300m",
        technique="embedding",
        model_id="google/embeddinggemma-300m",
        runtime="tei",
        endpoint_env="RAG_EMBEDDING_URL_EMBEDDINGGEMMA_300M",
        used_by=("indexing", "dense", "hybrid", "hybrid_rerank"),
        description="낮은 운영 비용의 소형 임베딩 모델",
    ),
    ModelService(
        key="reranker-bge-m3",
        technique="reranking",
        model_id="BAAI/bge-reranker-v2-m3",
        runtime="tei",
        endpoint_env="RAG_RERANKER_URL",
        used_by=("hybrid_rerank",),
        description="hybrid top-k 근거를 재정렬하는 cross-encoder",
    ),
    ModelService(
        key="ocr-tesseract-kor-eng",
        technique="ocr",
        model_id="tesseract:kor+eng",
        runtime="host-binary",
        endpoint_env=None,
        used_by=("scanned_pdf", "image_source"),
        description="스캔 PDF·이미지의 한국어/영어 텍스트 인식",
    ),
)


EMBEDDING_SERVICE_BY_SELECTION = {
    "BGE-M3": "embedding-bge-m3",
    "Qwen3-Embedding-0.6B": "embedding-qwen3-0-6b",
    "EmbeddingGemma-300M": "embedding-gemma-300m",
}


def service_for_key(key: str) -> ModelService | None:
    return next((service for service in MODEL_SERVICES if service.key == key), None)


def service_status(service: ModelService) -> dict:
    payload = asdict(service)
    if service.runtime == "host-binary":
        executable = shutil.which("tesseract")
        return {
            **payload,
            "endpoint": None,
            "configured": bool(executable),
            "ready": bool(executable),
            "status": "READY" if executable else "NOT_INSTALLED",
            "detail": executable or "Tesseract 실행 파일과 kor/eng language pack이 필요합니다.",
        }
    endpoint = os.getenv(service.endpoint_env or "")
    if not endpoint:
        return {
            **payload,
            "endpoint": None,
            "configured": False,
            "ready": False,
            "status": "NOT_CONFIGURED",
            "detail": f"{service.endpoint_env} 환경변수를 설정해 주세요.",
        }
    try:
        response = httpx.get(endpoint.rstrip("/") + "/health", timeout=0.8)
        response.raise_for_status()
        return {
            **payload,
            "endpoint": endpoint,
            "configured": True,
            "ready": True,
            "status": "READY",
            "detail": "모델 서비스가 요청을 받을 준비가 되었습니다.",
        }
    except Exception as error:
        return {
            **payload,
            "endpoint": endpoint,
            "configured": True,
            "ready": False,
            "status": "UNAVAILABLE",
            "detail": f"모델 서비스 상태를 확인하지 못했습니다: {error}",
        }


def runtime_catalog() -> list[dict]:
    return [service_status(service) for service in MODEL_SERVICES]


def execution_plan(
    *, embedding_model: str, document_profiles: Iterable[str], retrieval_configs: Iterable[str]
) -> dict:
    required_keys = [EMBEDDING_SERVICE_BY_SELECTION[embedding_model]]
    profiles = set(document_profiles)
    retrievals = set(retrieval_configs)
    if profiles & {"scanned"}:
        required_keys.append("ocr-tesseract-kor-eng")
    if "hybrid_rerank" in retrievals:
        required_keys.append("reranker-bge-m3")
    requirements = [service_status(service_for_key(key)) for key in required_keys if service_for_key(key)]
    return {
        "embedding_model": embedding_model,
        "required_services": requirements,
        "ready": all(service["ready"] for service in requirements),
        "fallback_policy": "development fallback is recorded in output metadata; production mode should require all listed services.",
    }
