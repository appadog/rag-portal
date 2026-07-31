"""Grounded local-generator client.

The generator receives only retrieval context. It must return sentence-level
citation IDs; the API layer validates them before any model text is exposed.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from time import perf_counter
from typing import Iterable

import httpx


class GenerationEndpointError(RuntimeError):
    """The configured local generator could not produce a usable response."""


@dataclass(frozen=True)
class GenerationSentence:
    text: str
    citation_ids: list[str]


@dataclass(frozen=True)
class GenerationResult:
    sentences: list[GenerationSentence]
    provider: str
    model: str | None
    latency_ms: int


def generator_endpoint() -> str | None:
    return os.getenv("RAG_GENERATOR_URL")


def generate_grounded(*, question: str, contexts: Iterable[dict]) -> GenerationResult:
    """Call the local endpoint with retrieval context and no other source text.

    Expected response schema::

      {"sentences": [{"text": "...", "citation_ids": ["segment-id"]}],
       "provider": "local-vllm", "model": "..."}

    A malformed response is intentionally an endpoint error, not a best-effort
    answer: the caller will use an explicit extractive fallback instead.
    """
    endpoint = generator_endpoint()
    if not endpoint:
        raise GenerationEndpointError("RAG_GENERATOR_URL is not configured")
    context_items = [
        {"segment_id": str(context["segment_id"]), "text": str(context["text"])}
        for context in contexts
    ]
    if not context_items:
        raise GenerationEndpointError("grounded generation requires retrieved context")
    started = perf_counter()
    try:
        response = httpx.post(
            endpoint.rstrip("/") + "/generate",
            json={
                "question": question,
                "contexts": context_items,
                "response_schema": {
                    "sentences": [{"text": "string", "citation_ids": ["segment_id"]}],
                },
            },
            timeout=float(os.getenv("RAG_GENERATOR_TIMEOUT_SECONDS", "15")),
        )
        response.raise_for_status()
        body = response.json()
    except Exception as error:
        raise GenerationEndpointError(f"local generator request failed: {error}") from error

    raw_sentences = body.get("sentences") if isinstance(body, dict) else None
    if not isinstance(raw_sentences, list) or not raw_sentences:
        raise GenerationEndpointError("local generator returned no sentence-level citations")
    sentences = []
    for item in raw_sentences:
        if not isinstance(item, dict):
            raise GenerationEndpointError("local generator returned an invalid sentence")
        text = item.get("text")
        citation_ids = item.get("citation_ids")
        if not isinstance(text, str) or not isinstance(citation_ids, list):
            raise GenerationEndpointError("local generator omitted text or citation_ids")
        sentences.append(GenerationSentence(text=text, citation_ids=[str(value) for value in citation_ids]))
    return GenerationResult(
        sentences=sentences,
        provider=str(body.get("provider") or "local-grounded-generator"),
        model=str(body["model"]) if body.get("model") is not None else os.getenv("RAG_GENERATOR_MODEL"),
        latency_ms=int((perf_counter() - started) * 1000),
    )
