"""Opt-in release gate against provisioned, non-fallback model services.

This suite intentionally never monkeypatches embeddings, reranking, generation,
or OCR. It is skipped in ordinary local/unit-test runs; once any release-model
endpoint is configured it becomes strict and refuses unavailable services or
fallback output.
"""
from __future__ import annotations

import base64
import hashlib
from io import BytesIO
import os
import time

from fastapi.testclient import TestClient
import fitz
from docx import Document as DocxDocument
from PIL import Image, ImageDraw, ImageFont
import pytest
import pytesseract

from app.main import app


client = TestClient(app)

REQUIRED_ENDPOINT_ENVS = (
    "RAG_EMBEDDING_URL_BGE_M3",
    "RAG_EMBEDDING_URL_QWEN3_EMBEDDING_0_6B",
    "RAG_EMBEDDING_URL_EMBEDDINGGEMMA_300M",
    "RAG_RERANKER_URL",
    "RAG_GENERATOR_URL",
)
CORE_SERVICE_KEYS = {
    "embedding-bge-m3",
    "embedding-qwen3-0-6b",
    "embedding-gemma-300m",
    "reranker-bge-m3",
    "generator-grounded",
}


def release_gate_requested() -> bool:
    return os.getenv("RAG_RELEASE_GATE") == "1" or any(os.getenv(name) for name in REQUIRED_ENDPOINT_ENVS)


def require_release_runtime(record_property: pytest.RecordProperty) -> dict[str, dict]:
    if not release_gate_requested():
        pytest.skip(
            "release-gate runtime is absent: set RAG_RELEASE_GATE=1 with all embedding, reranker, and generator endpoints"
        )
    missing = [name for name in REQUIRED_ENDPOINT_ENVS if not os.getenv(name)]
    if missing:
        pytest.fail(f"release gate requested/configured but required endpoint env is missing: {', '.join(missing)}")
    if not os.getenv("RAG_PORTAL_DB_PATH"):
        pytest.fail("release gate requires an isolated RAG_PORTAL_DB_PATH; do not run against a developer snapshot")
    runtime = client.get("/api/v1/model-runtime")
    assert runtime.status_code == 200
    services = {service["key"]: service for service in runtime.json()["services"]}
    configured_not_ready = [
        f"{key}={service['status']}"
        for key, service in services.items()
        if service["configured"] and not service["ready"]
    ]
    assert not configured_not_ready, f"configured model runtime is not READY: {', '.join(configured_not_ready)}"
    missing_or_unready = [
        key for key in CORE_SERVICE_KEYS
        if key not in services or not services[key]["ready"]
    ]
    assert not missing_or_unready, f"release runtime must be READY: {', '.join(sorted(missing_or_unready))}"
    record_property("runtime_services", ",".join(f"{key}:{services[key]['status']}" for key in sorted(CORE_SERVICE_KEYS)))
    return services


def wait_for_job(job_id: str) -> dict:
    timeout_seconds = float(os.getenv("RAG_RELEASE_GATE_JOB_TIMEOUT_SECONDS", "120"))
    deadline = time.monotonic() + timeout_seconds
    latest: dict | None = None
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/rag-jobs/{job_id}")
        assert response.status_code == 200
        latest = response.json()
        if latest["state"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            break
        time.sleep(0.2)
    assert latest is not None and latest["state"] == "SUCCEEDED", f"job did not succeed: {latest}"
    return latest


def create_instance() -> str:
    response = client.post(
        "/api/v1/rag-instances",
        json={"name": "Sprint 11 release gate", "questionnaire": {"primary_language": "ko", "embedding_model": "BGE-M3"}},
    )
    assert response.status_code == 201
    return response.json()["id"]


def finalize_candidate(instance_id: str, document_id: str, question: str, retrieval_config: str) -> dict:
    comparison = client.post(
        f"/api/v1/rag-instances/{instance_id}/tuning/compare",
        json={"document_ids": [document_id], "question": question},
    )
    assert comparison.status_code == 200
    result = next(
        item for item in comparison.json()["results"]
        if item["candidate_state"] == "READY" and item["candidate"]["retrieval_config"] == retrieval_config
    )
    assert result["generation"]["mode"] == "MODEL", result["generation"]
    assert result["generation"]["fallback"] is False
    assert result["generation"]["grounding_valid"] is True
    assert "fallback" not in (result["generation"]["provider"] or "").lower()
    vote = client.post(
        f"/api/v1/tuning-rounds/{comparison.json()['round']['id']}/vote",
        json={"candidate_ids": [result["candidate"]["id"]]},
    )
    assert vote.status_code == 200
    finalized = client.post(f"/api/v1/rag-instances/{instance_id}/tuning/finalize", json={"document_id": document_id})
    assert finalized.status_code == 200
    return finalized.json()


def assert_model_grounded(response: dict, expected_document_ids: set[str] | None = None) -> None:
    assert response["grounded"] is True
    assert response["generation"]["mode"] == "MODEL", response["generation"]
    assert response["generation"]["fallback"] is False
    assert response["generation"]["grounding_valid"] is True
    assert response["citations"]
    supplied = set(response["generation"]["supplied_segment_ids"])
    assert {citation["segment_id"] for citation in response["citations"]} <= supplied
    if expected_document_ids:
        assert {citation["document_id"] for citation in response["citations"]} <= expected_document_ids


def make_docx_bytes(paragraphs: list[str]) -> bytes:
    document = DocxDocument()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def make_pdf_bytes(paragraphs: list[str]) -> bytes:
    document = fitz.open()
    for paragraph in paragraphs:
        page = document.new_page()
        page.insert_text((72, 72), paragraph)
    return document.tobytes()


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def test_release_gate_real_runtime_end_to_end(monkeypatch: pytest.MonkeyPatch, record_property: pytest.RecordProperty) -> None:
    require_release_runtime(record_property)
    benchmark = client.post("/api/v1/embedding-benchmarks/run")
    assert benchmark.status_code == 200
    benchmark_body = benchmark.json()
    assert all(result["status"] == "COMPLETED" and result["provider"] == "local-tei" for result in benchmark_body["results"]), benchmark_body
    record_property("benchmark_run_id", benchmark_body["run"]["id"])

    instance_id = create_instance()
    question = "출장 사전 승인 요건과 해외 식비 한도는?"
    text_fixture = "출장은 사전에 승인을 받아야 합니다.\n해외 출장 식비는 하루 150달러를 한도로 합니다."
    record_property("text_fixture_sha256", sha256(text_fixture.encode()))
    uploaded = client.post(
        f"/api/v1/rag-instances/{instance_id}/documents",
        json={
            "documents": [
                {"filename": "approval.txt", "content": "출장은 사전에 승인을 받아야 합니다."},
                {"filename": "meal.txt", "content": "해외 출장 식비는 하루 150달러를 한도로 합니다."},
            ]
        },
    )
    assert uploaded.status_code == 202
    upload_body = uploaded.json()
    wait_for_job(upload_body["job"]["id"])
    approval_id, meal_id = (document["id"] for document in upload_body["documents"])
    finalize_candidate(instance_id, approval_id, question, "dense")
    finalize_candidate(instance_id, meal_id, question, "hybrid_rerank")

    single = client.post(
        f"/api/v1/rag-instances/{instance_id}/search",
        json={"document_ids": [approval_id], "question": "출장 사전 승인 요건은?"},
    )
    assert single.status_code == 200
    assert_model_grounded(single.json(), {approval_id})

    multi = client.post(
        f"/api/v1/rag-instances/{instance_id}/search",
        json={"document_ids": [approval_id, meal_id], "question": question},
    )
    assert multi.status_code == 200
    multi_body = multi.json()
    assert_model_grounded(multi_body, {approval_id, meal_id})
    assert multi_body["retrieval_metadata"]["mode"] == "MULTI_DOCUMENT"
    assert all(item["ranking"]["provider"] == "local-tei" for item in multi_body["retrieval_metadata"]["documents"])
    assert multi_body["retrieval_metadata"]["documents"][1]["rerank"]["provider"] == "local-tei-cross-encoder"
    assert "fallback" not in multi_body["retrieval_metadata"]["documents"][1]["rerank"]["provider"]
    record_property("single_answer_artifact", single.json()["artifact"]["id"])
    record_property("multi_answer_artifact", multi_body["artifact"]["id"])

    # Force the documented bounded comparison path while retaining actual DOCX
    # and PDF parsing, indexing, generation, and full-reindex provider calls.
    monkeypatch.setenv("RAG_PORTAL_COMPARISON_CHUNK_THRESHOLD", "3")
    paragraphs = [f"제{index}조 국내 출장 숙박비는 1박 10만원을 한도로 하며 사전 승인이 필요합니다." for index in range(1, 11)]
    docx_bytes = make_docx_bytes(paragraphs)
    pdf_bytes = make_pdf_bytes(paragraphs)
    record_property("large_docx_sha256", sha256(docx_bytes))
    record_property("large_pdf_sha256", sha256(pdf_bytes))
    large_upload = client.post(
        f"/api/v1/rag-instances/{instance_id}/documents",
        json={
            "documents": [
                {
                    "filename": "large-policy.docx",
                    "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "content_base64": base64.b64encode(docx_bytes).decode(),
                },
                {
                    "filename": "large-policy.pdf",
                    "content_type": "application/pdf",
                    "content_base64": base64.b64encode(pdf_bytes).decode(),
                },
            ]
        },
    )
    assert large_upload.status_code == 202
    large_body = large_upload.json()
    wait_for_job(large_body["job"]["id"])
    docx_id, pdf_id = (document["id"] for document in large_body["documents"])
    detail = client.get(f"/api/v1/rag-instances/{instance_id}").json()
    large_documents = {document["id"]: document for document in detail["documents"]}
    assert large_documents[docx_id]["parser"] == "python-docx"
    assert large_documents[pdf_id]["parser"] == "pypdf"
    assert all(large_documents[document_id]["comparison"]["scope"] == "SAMPLE" for document_id in (docx_id, pdf_id))
    finalized = finalize_candidate(instance_id, docx_id, "국내 출장 숙박비 한도는?", "dense")
    reindex = finalized["full_reindex"]
    assert reindex["required"] is True
    reindex_job = wait_for_job(reindex["job"]["id"])
    assert reindex_job["kind"] == "FULL_REINDEX"
    after_reindex = client.get(f"/api/v1/rag-instances/{instance_id}").json()
    reindex_state = next(document for document in after_reindex["documents"] if document["id"] == docx_id)["full_reindex"]
    assert reindex_state["search_eligible"] is True
    reindexed_search = client.post(
        f"/api/v1/rag-instances/{instance_id}/search",
        json={"document_ids": [docx_id], "question": "국내 출장 숙박비 한도는?"},
    )
    assert reindexed_search.status_code == 200
    assert_model_grounded(reindexed_search.json(), {docx_id})
    record_property("full_reindex_job", reindex_job["id"])
    record_property("full_reindex_artifact", reindex["artifact"]["id"])


def test_release_gate_ocr_fixture_when_kor_and_eng_are_available(record_property: pytest.RecordProperty) -> None:
    services = require_release_runtime(record_property)
    try:
        languages = set(pytesseract.get_languages(config=""))
    except Exception as error:  # pragma: no cover - external runtime gate
        pytest.skip(f"OCR release fixture skipped: cannot inspect Tesseract languages ({error})")
    if not {"kor", "eng"} <= languages:
        pytest.skip("OCR release fixture skipped: Tesseract kor+eng language data is not installed")
    assert services["ocr-tesseract-kor-eng"]["ready"] is True
    image = Image.new("RGB", (1200, 220), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 54)
    except OSError:  # pragma: no cover - host font availability
        pytest.skip("OCR release fixture skipped: DejaVuSans font is unavailable")
    draw.text((30, 70), "Travel meal limit 150 dollars", fill="black", font=font)
    output = BytesIO()
    image.save(output, format="PNG")
    image_bytes = output.getvalue()
    record_property("ocr_fixture_sha256", sha256(image_bytes))
    instance_id = create_instance()
    uploaded = client.post(
        f"/api/v1/rag-instances/{instance_id}/documents",
        json={
            "documents": [{
                "filename": "ocr-release-fixture.png",
                "content_type": "image/png",
                "content_base64": base64.b64encode(image_bytes).decode(),
            }]
        },
    )
    assert uploaded.status_code == 202
    wait_for_job(uploaded.json()["job"]["id"])
    document = client.get(f"/api/v1/rag-instances/{instance_id}").json()["documents"][0]
    assert document["used_ocr"] is True
    assert document["parser"] == "pillow+tesseract"
    record_property("ocr_document_id", document["id"])
