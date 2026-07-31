"""Provider-backed embeddings and reproducible local BM25/vector retrieval."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import math
import os
import re
from time import perf_counter

import httpx


MODEL_IDS = {
    "BGE-M3": "BAAI/bge-m3",
    "Qwen3-Embedding-0.6B": "Qwen/Qwen3-Embedding-0.6B",
    "EmbeddingGemma-300M": "google/embeddinggemma-300m",
}


def local_embedding_url(model_name: str) -> str | None:
    key = "RAG_EMBEDDING_URL_" + re.sub(r"[^A-Za-z0-9]+", "_", model_name).upper().strip("_")
    return os.getenv(key) or os.getenv("RAG_EMBEDDING_URL")


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    provider: str
    dimension: int
    latency_ms: int
    warning: str | None = None


def tokenize(value: str) -> list[str]:
    normalized = re.sub(r"[^0-9A-Za-z가-힣]+", " ", value.lower())
    words = [word for word in normalized.split() if len(word) > 1]
    compact = re.sub(r"\s+", "", normalized)
    return words + [compact[index : index + 2] for index in range(max(0, len(compact) - 1))]


def hash_embeddings(texts: list[str], dimension: int = 96) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        vector = [0.0] * dimension
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % dimension
            vector[bucket] += -1.0 if digest[4] % 2 else 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        vectors.append([value / norm for value in vector])
    return vectors


def embed(texts: list[str], model_name: str) -> EmbeddingBatch:
    started = perf_counter()
    endpoint = local_embedding_url(model_name)
    if endpoint:
        try:
            response = httpx.post(
                endpoint.rstrip("/") + "/embed",
                json={"inputs": texts},
                timeout=float(os.getenv("RAG_EMBEDDING_TIMEOUT_SECONDS", "60")),
            )
            response.raise_for_status()
            raw = response.json()
            vectors = [[float(value) for value in vector] for vector in raw]
            return EmbeddingBatch(
                vectors=vectors,
                provider="local-tei",
                dimension=len(vectors[0]) if vectors else 0,
                latency_ms=int((perf_counter() - started) * 1000),
            )
        except Exception as error:
            local_error = f"로컬 TEI 임베딩 endpoint 호출에 실패했습니다: {error}"
    else:
        local_error = "로컬 TEI 임베딩 endpoint가 설정되지 않았습니다."
    token = os.getenv("HF_TOKEN")
    if not token:
        vectors = hash_embeddings(texts)
        return EmbeddingBatch(
            vectors=vectors,
            provider="local-hash-fallback",
            dimension=len(vectors[0]) if vectors else 0,
            latency_ms=int((perf_counter() - started) * 1000),
            warning=f"{local_error} HF_TOKEN도 없어 로컬 해시 임베딩을 사용했습니다. 의미 검색 품질은 실측 대상이 아닙니다.",
        )
    try:
        from huggingface_hub import InferenceClient

        client = InferenceClient(provider=os.getenv("HF_EMBEDDING_PROVIDER", "hf-inference"), api_key=token)
        response = client.feature_extraction(texts, model=MODEL_IDS.get(model_name, model_name))
        raw = response.tolist() if hasattr(response, "tolist") else response
        vectors = [[float(value) for value in vector] for vector in raw]
        return EmbeddingBatch(
            vectors=vectors,
            provider="huggingface-inference",
            dimension=len(vectors[0]) if vectors else 0,
            latency_ms=int((perf_counter() - started) * 1000),
        )
    except Exception as error:
        vectors = hash_embeddings(texts)
        return EmbeddingBatch(
            vectors=vectors,
            provider="local-hash-fallback",
            dimension=len(vectors[0]) if vectors else 0,
            latency_ms=int((perf_counter() - started) * 1000),
            warning=f"임베딩 provider 호출에 실패해 로컬 기준선으로 전환했습니다: {error}",
        )


def cosine(left: list[float], right: list[float]) -> float:
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


def bm25_scores(query: str, texts: list[str], *, k1: float = 1.5, b: float = 0.75) -> list[float]:
    documents = [tokenize(text) for text in texts]
    query_tokens = set(tokenize(query))
    if not documents or not query_tokens:
        return [0.0] * len(documents)
    document_frequency = Counter(token for document in documents for token in set(document))
    average_length = sum(len(document) for document in documents) / len(documents) or 1.0
    scores = []
    for document in documents:
        frequencies = Counter(document)
        score = 0.0
        for token in query_tokens:
            if token not in frequencies:
                continue
            inverse_frequency = math.log(1 + (len(documents) - document_frequency[token] + 0.5) / (document_frequency[token] + 0.5))
            numerator = frequencies[token] * (k1 + 1)
            denominator = frequencies[token] + k1 * (1 - b + b * len(document) / average_length)
            score += inverse_frequency * numerator / denominator
        scores.append(score)
    return scores


def normalize(scores: list[float]) -> list[float]:
    maximum = max(scores, default=0.0)
    return [score / maximum if maximum else 0.0 for score in scores]


def rerank_score(query: str, text: str) -> float:
    """Local rerank fallback: coverage and phrase continuity after hybrid retrieval."""
    query_tokens = set(tokenize(query))
    text_tokens = set(tokenize(text))
    coverage = len(query_tokens & text_tokens) / len(query_tokens) if query_tokens else 0.0
    compact_query = re.sub(r"\s+", "", query.lower())
    compact_text = re.sub(r"\s+", "", text.lower())
    phrase = 1.0 if len(compact_query) > 2 and compact_query in compact_text else 0.0
    return min(1.0, coverage * 0.85 + phrase * 0.15)


def rerank(query: str, texts: list[str]) -> tuple[list[float], str, str | None]:
    endpoint = os.getenv("RAG_RERANKER_URL")
    if endpoint:
        try:
            response = httpx.post(
                endpoint.rstrip("/") + "/rerank",
                json={"query": query, "texts": texts, "raw_scores": False},
                timeout=float(os.getenv("RAG_RERANKER_TIMEOUT_SECONDS", "60")),
            )
            response.raise_for_status()
            ordered = response.json()
            scores = [0.0] * len(texts)
            for item in ordered:
                scores[int(item["index"])] = float(item["score"])
            return normalize(scores), "local-tei-cross-encoder", None
        except Exception as error:
            warning = f"로컬 cross-encoder reranker 호출에 실패했습니다: {error}"
    else:
        warning = "로컬 cross-encoder reranker endpoint가 설정되지 않았습니다."
    return [rerank_score(query, text) for text in texts], "local-heuristic-fallback", warning


def rank(
    *, query: str, texts: list[str], vectors: list[list[float]], retrieval_config: str, model_name: str
) -> tuple[list[float], EmbeddingBatch, dict]:
    query_batch = embed([query], model_name)
    dense = [max(0.0, cosine(query_batch.vectors[0], vector)) for vector in vectors]
    bm25 = bm25_scores(query, texts)
    normalized_dense, normalized_bm25 = normalize(dense), normalize(bm25)
    if retrieval_config == "dense":
        return normalized_dense, query_batch, {"reranker_provider": None, "reranker_warning": None}
    if retrieval_config == "bm25":
        return normalized_bm25, query_batch, {"reranker_provider": None, "reranker_warning": None}
    hybrid = [0.55 * vector + 0.45 * lexical for vector, lexical in zip(normalized_dense, normalized_bm25)]
    if retrieval_config == "hybrid_rerank":
        rerank_scores, provider, warning = rerank(query, texts)
        return [0.7 * base + 0.3 * score for base, score in zip(hybrid, rerank_scores)], query_batch, {
            "reranker_provider": provider,
            "reranker_warning": warning,
        }
    return hybrid, query_batch, {"reranker_provider": None, "reranker_warning": None}
