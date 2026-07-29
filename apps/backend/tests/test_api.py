import time

from fastapi.testclient import TestClient

from app import main
from app.main import app


client = TestClient(app)


def test_openapi_includes_workspace_state_contract() -> None:
    schema = client.get("/api/v1/openapi.json")
    assert schema.status_code == 200
    paths = schema.json()["paths"]
    assert "/api/v1/rag-instances/{instance_id}/jobs" in paths
    assert "/api/v1/rag-instances/{instance_id}/artifacts" in paths
    assert "/api/v1/documents/{document_id}/segments/{segment_id}" in paths


def test_loopback_vite_ports_are_allowed_by_cors() -> None:
    response = client.options(
        "/api/v1/rag-instances",
        headers={
            "Origin": "http://127.0.0.1:5175",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5175"


def create_instance() -> str:
    response = client.post("/api/v1/rag-instances", json={"name": "출장 규정", "questionnaire": {"primary_language": "ko", "multi_hop_questions": False}})
    assert response.status_code == 201
    assert response.json()["embedding_model"] == "BGE-M3"
    return response.json()["id"]


def wait_for_job(job_id: str) -> dict:
    for _ in range(50):
        response = client.get(f"/api/v1/rag-jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["state"] in {"SUCCEEDED", "FAILED"}:
            return job
        time.sleep(0.01)
    raise AssertionError("job did not reach a terminal state")


def test_create_upload_compare_vote_finalize_and_search() -> None:
    instance_id = create_instance()
    upload = client.post(
        f"/api/v1/rag-instances/{instance_id}/documents",
        json={"documents": [{"filename": "출장비_규정.txt", "content": "제5조 해외 출장 식비는 국가 등급에 따라 1일 80~150달러를 한도로 지급합니다.\n\n제7조 국내 출장 숙박비는 1박 10만원을 한도로 합니다."}]},
    )
    assert upload.status_code == 202
    assert upload.json()["job"]["state"] in {"QUEUED", "PARSING", "GENERATING_CANDIDATES", "INDEXING"}
    assert wait_for_job(upload.json()["job"]["id"])["state"] == "SUCCEEDED"
    document_id = upload.json()["documents"][0]["id"]

    comparison = client.post(f"/api/v1/rag-instances/{instance_id}/tuning/compare", json={"document_ids": [document_id], "question": "국내 출장 숙박비 한도는?"})
    assert comparison.status_code == 200
    first = comparison.json()["results"][0]
    assert "candidate" in first and "citations" in first

    vote = client.post(f"/api/v1/tuning-rounds/{comparison.json()['round']['id']}/vote", json={"candidate_ids": [first["candidate"]["id"]]})
    assert vote.status_code == 200
    assert vote.json()["tuning_status"]["can_finalize"] is True

    finalized = client.post(f"/api/v1/rag-instances/{instance_id}/tuning/finalize", json={"document_id": document_id})
    assert finalized.status_code == 200
    assert finalized.json()["instance"]["status"] == "READY"

    searched = client.post(f"/api/v1/rag-instances/{instance_id}/search", json={"document_ids": [document_id], "question": "국내 출장 숙박비 한도는?", "sensitivity": "balanced"})
    assert searched.status_code == 200
    assert searched.json()["grounded"] is True
    assert "10만원" in searched.json()["answer"]


def test_tied_candidates_cannot_finalize() -> None:
    instance_id = create_instance()
    upload = client.post(f"/api/v1/rag-instances/{instance_id}/documents", json={"documents": [{"filename": "notes.txt", "content": "휴가는 연차 규정에 따라 신청합니다."}]})
    document_id = upload.json()["documents"][0]["id"]
    assert wait_for_job(upload.json()["job"]["id"])["state"] == "SUCCEEDED"
    comparison = client.post(f"/api/v1/rag-instances/{instance_id}/tuning/compare", json={"document_ids": [document_id], "question": "휴가는 어떻게 신청해?"}).json()
    candidate_ids = [result["candidate"]["id"] for result in comparison["results"][:2]]
    client.post(f"/api/v1/tuning-rounds/{comparison['round']['id']}/vote", json={"candidate_ids": candidate_ids})
    finalized = client.post(f"/api/v1/rag-instances/{instance_id}/tuning/finalize", json={"document_id": document_id})
    assert finalized.status_code == 409
    assert finalized.json()["detail"]["code"] == "TUNING_TIED_OR_UNVOTED"


def test_ungrounded_query_is_refused() -> None:
    instance_id = create_instance()
    upload = client.post(f"/api/v1/rag-instances/{instance_id}/documents", json={"documents": [{"filename": "policy.txt", "content": "연차 휴가는 사전 승인이 필요합니다."}]})
    document_id = upload.json()["documents"][0]["id"]
    assert wait_for_job(upload.json()["job"]["id"])["state"] == "SUCCEEDED"
    comparison = client.post(f"/api/v1/rag-instances/{instance_id}/tuning/compare", json={"document_ids": [document_id], "question": "연차 휴가"}).json()
    candidate_id = comparison["results"][0]["candidate"]["id"]
    client.post(f"/api/v1/tuning-rounds/{comparison['round']['id']}/vote", json={"candidate_ids": [candidate_id]})
    client.post(f"/api/v1/rag-instances/{instance_id}/tuning/finalize", json={"document_id": document_id})
    response = client.post(f"/api/v1/rag-instances/{instance_id}/search", json={"document_ids": [document_id], "question": "화성 이주 비용은?", "sensitivity": "strict"})
    assert response.status_code == 200
    assert response.json()["grounded"] is False


def test_candidate_pipelines_use_distinct_persisted_chunks_and_citations() -> None:
    instance_id = create_instance()
    content = """제1조 목적
이 문서는 출장 절차와 비용 기준을 설명합니다. 신청은 사전에 승인받아야 합니다.

제2조 국내 출장
국내 출장 숙박비는 1박 10만원을 한도로 합니다. 교통비는 영수증 기준으로 정산합니다.

제3조 해외 출장
해외 출장 식비는 국가 등급에 따라 1일 80~150달러입니다. 항공료는 사전 승인을 받아야 합니다."""
    upload = client.post(
        f"/api/v1/rag-instances/{instance_id}/documents",
        json={"documents": [{"filename": "travel-policy.txt", "content": content}]},
    ).json()
    assert wait_for_job(upload["job"]["id"])["state"] == "SUCCEEDED"
    document_id = upload["documents"][0]["id"]
    document = main.INSTANCES[instance_id].documents[document_id]
    candidates = [main.CANDIDATES[candidate_id] for candidate_id in document.candidate_ids]
    semantic_candidate = next(candidate for candidate in candidates if candidate.chunking_strategy == "semantic")
    hierarchical_candidate = next(candidate for candidate in candidates if candidate.chunking_strategy == "hierarchical")
    assert len(semantic_candidate.segments) == 1
    assert len(hierarchical_candidate.segments) == 3
    assert {segment.id for segment in semantic_candidate.segments}.isdisjoint(
        {segment.id for segment in hierarchical_candidate.segments}
    )

    comparison = client.post(
        f"/api/v1/rag-instances/{instance_id}/tuning/compare",
        json={"document_ids": [document_id], "question": "국내 출장 숙박비 한도는?"},
    ).json()
    result = next(item for item in comparison["results"] if item["candidate"]["id"] == hierarchical_candidate.id)
    assert result["candidate"]["chunk_count"] == 3
    citation = result["citations"][0]
    assert citation["segment_id"] in {segment.id for segment in hierarchical_candidate.segments}
    assert client.get(citation["navigate_url"]).status_code == 200


def finalize_single_document(instance_id: str, content: str = "제7조 국내 출장 숙박비는 1박 10만원을 한도로 합니다.") -> str:
    upload = client.post(f"/api/v1/rag-instances/{instance_id}/documents", json={"documents": [{"filename": "policy.txt", "content": content}]})
    document_id = upload.json()["documents"][0]["id"]
    assert wait_for_job(upload.json()["job"]["id"])["state"] == "SUCCEEDED"
    comparison = client.post(f"/api/v1/rag-instances/{instance_id}/tuning/compare", json={"document_ids": [document_id], "question": "국내 출장 숙박비 한도는?"}).json()
    winner_id = comparison["results"][0]["candidate"]["id"]
    assert client.post(f"/api/v1/tuning-rounds/{comparison['round']['id']}/vote", json={"candidate_ids": [winner_id]}).status_code == 200
    assert client.post(f"/api/v1/rag-instances/{instance_id}/tuning/finalize", json={"document_id": document_id}).status_code == 200
    return document_id


def test_job_metadata_and_reuse_or_retune_contract() -> None:
    instance_id = create_instance()
    initial = client.post(f"/api/v1/rag-instances/{instance_id}/documents", json={"documents": [{"filename": "travel.txt", "content": "제7조 국내 출장 숙박비는 1박 10만원을 한도로 합니다."}], "pipeline_mode": "retune"})
    assert initial.status_code == 202
    job = initial.json()["job"]
    assert job["state"] in {"QUEUED", "PARSING", "GENERATING_CANDIDATES", "INDEXING"}
    completed_job = wait_for_job(job["id"])
    assert [stage["key"] for stage in completed_job["stages"]] == ["PARSING", "CANDIDATES", "INDEXING"]
    assert all(stage["state"] == "SUCCEEDED" for stage in completed_job["stages"])
    assert initial.json()["artifact"]["type"] == "PROCESSING_RUN"
    document_id = initial.json()["documents"][0]["id"]

    comparison = client.post(f"/api/v1/rag-instances/{instance_id}/tuning/compare", json={"document_ids": [document_id], "question": "숙박비는?"}).json()
    winner_id = comparison["results"][0]["candidate"]["id"]
    client.post(f"/api/v1/tuning-rounds/{comparison['round']['id']}/vote", json={"candidate_ids": [winner_id]})
    client.post(f"/api/v1/rag-instances/{instance_id}/tuning/finalize", json={"document_id": document_id})

    options = client.get(f"/api/v1/rag-instances/{instance_id}/document-add-options")
    assert options.status_code == 200
    assert options.json()["default_mode"] == "reuse"
    assert options.json()["reusable_sources"][0]["document_id"] == document_id

    reused = client.post(f"/api/v1/rag-instances/{instance_id}/documents", json={"documents": [{"filename": "travel-extra.txt", "content": "출장은 사전 승인 후 진행합니다."}], "pipeline_mode": "reuse", "reuse_from_document_id": document_id})
    assert reused.status_code == 202
    assert wait_for_job(reused.json()["job"]["id"])["state"] == "SUCCEEDED"
    assert reused.json()["decision"]["next_action"] == "SEARCH_READY"
    refreshed = client.get(f"/api/v1/rag-instances/{instance_id}").json()
    assert any(document["finalized_candidate_id"] for document in refreshed["documents"] if document["id"] != document_id)
    assert client.get(f"/api/v1/rag-instances/{instance_id}/jobs").json()["total"] == 2
    artifact_types = {item["type"] for item in client.get(f"/api/v1/rag-instances/{instance_id}/artifacts").json()["items"]}
    assert {"PROCESSING_RUN", "TUNING_COMPARISON", "PIPELINE_DECISION"} <= artifact_types


def test_citation_navigation_feedback_signal_retune_and_document_delete() -> None:
    instance_id = create_instance()
    document_id = finalize_single_document(instance_id)
    searched = client.post(f"/api/v1/rag-instances/{instance_id}/search", json={"document_ids": [document_id], "question": "국내 출장 숙박비 한도는?"})
    assert searched.status_code == 200
    search_body = searched.json()
    citation = search_body["citations"][0]
    viewer = client.get(citation["navigate_url"])
    assert viewer.status_code == 200
    assert viewer.json()["viewer"]["highlight"]["segment_id"] == citation["segment_id"]

    for _ in range(3):
        feedback = client.post(f"/api/v1/rag-instances/{instance_id}/feedback", json={"rating": -1, "artifact_id": search_body["artifact"]["id"], "document_ids": [document_id], "citation_ids": [citation["id"]]})
        assert feedback.status_code == 201
    assert feedback.json()["retuning_signal"]["recommended"] is True
    assert client.get(f"/api/v1/rag-instances/{instance_id}/feedback-summary").json()["negative_count"] == 3

    retune = client.post(f"/api/v1/rag-instances/{instance_id}/retune", json={"document_ids": [document_id], "reason": "부정 피드백 확인"})
    assert retune.status_code == 202
    assert retune.json()["next_action"] == "TUNE_DOCUMENT"
    assert wait_for_job(retune.json()["job"]["id"])["state"] == "SUCCEEDED"
    refreshed = client.get(f"/api/v1/rag-instances/{instance_id}").json()
    assert len(refreshed["documents"][0]["candidates"]) == 9

    deleted = client.delete(f"/api/v1/rag-instances/{instance_id}/documents/{document_id}")
    assert deleted.status_code == 200
    assert deleted.json()["artifacts_with_unavailable_context"]


def test_job_and_comparison_are_restored_after_runtime_reload() -> None:
    instance_id = create_instance()
    upload = client.post(
        f"/api/v1/rag-instances/{instance_id}/documents",
        json={
            "documents": [
                {
                    "filename": "restore.txt",
                    "content": "제7조 국내 출장 숙박비는 1박 10만원을 한도로 합니다.",
                }
            ]
        },
    ).json()
    assert wait_for_job(upload["job"]["id"])["state"] == "SUCCEEDED"
    document_id = upload["documents"][0]["id"]
    comparison = client.post(
        f"/api/v1/rag-instances/{instance_id}/tuning/compare",
        json={"document_ids": [document_id], "question": "국내 출장 숙박비 한도는?"},
    ).json()
    winner_id = comparison["results"][0]["candidate"]["id"]
    assert client.post(
        f"/api/v1/tuning-rounds/{comparison['round']['id']}/vote",
        json={"candidate_ids": [winner_id]},
    ).status_code == 200

    main.persist_state()
    main.INSTANCES.clear()
    main.CANDIDATES.clear()
    main.JOBS.clear()
    main.ROUNDS.clear()
    main.ARTIFACTS.clear()
    main.FEEDBACK.clear()
    main.restore_state()

    restored = client.get(f"/api/v1/rag-instances/{instance_id}")
    assert restored.status_code == 200
    body = restored.json()
    assert body["latest_job"]["state"] == "SUCCEEDED"
    assert body["latest_round"]["id"] == comparison["round"]["id"]
    assert body["latest_round"]["results"][0]["candidate"]["selection_count"] == 1
    assert main.CANDIDATES[winner_id].segments
