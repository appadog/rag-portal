"""Dispatch contracts with thread fallback and optional Redis/SQS adapters."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from threading import Lock, Thread
from typing import Callable


QUEUE_KEY = "rag-portal:processing"
_LOCAL_DISPATCH_LOCK = Lock()
_LOCAL_IN_FLIGHT: set[str] = set()


@dataclass(frozen=True)
class DispatchReceipt:
    requested_backend: str
    backend: str
    message_id: str
    idempotency_key: str
    fallback_reason: str | None = None


def requested_backend() -> str:
    return os.getenv("RAG_QUEUE_BACKEND", "thread").lower()


def backend_status() -> dict:
    requested = requested_backend()
    if requested in {"thread", "local"}:
        return {"requested": requested, "effective": "thread", "ready": True, "detail": "local development thread adapter"}
    if requested == "redis":
        try:
            import redis

            client = redis.Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=0.5)
            client.ping()
            return {"requested": requested, "effective": "redis", "ready": True, "detail": "Redis list dispatch adapter"}
        except Exception as error:
            return {"requested": requested, "effective": "thread", "ready": False, "detail": f"Redis unavailable; local fallback: {error}"}
    if requested in {"sqs", "sqs_compatible"}:
        try:
            import boto3

            queue_url = os.environ["RAG_SQS_QUEUE_URL"]
            client = boto3.client("sqs", endpoint_url=os.getenv("RAG_SQS_ENDPOINT_URL") or None)
            client.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])
            return {"requested": requested, "effective": "sqs", "ready": True, "detail": "SQS-compatible dispatch adapter"}
        except Exception as error:
            return {"requested": requested, "effective": "thread", "ready": False, "detail": f"SQS unavailable; local fallback: {error}"}
    return {"requested": requested, "effective": "thread", "ready": False, "detail": "unsupported backend; local fallback"}


def backend_name() -> str:
    return backend_status()["effective"]


def _thread_dispatch(
    job_id: str,
    idempotency_key: str,
    run: Callable[[], None],
    *,
    requested: str = "thread",
    fallback_reason: str | None = None,
) -> DispatchReceipt:
    with _LOCAL_DISPATCH_LOCK:
        if idempotency_key in _LOCAL_IN_FLIGHT:
            return DispatchReceipt(requested, "thread", f"local-duplicate:{job_id}", idempotency_key, fallback_reason)
        _LOCAL_IN_FLIGHT.add(idempotency_key)

    def consume() -> None:
        try:
            run()
        finally:
            with _LOCAL_DISPATCH_LOCK:
                _LOCAL_IN_FLIGHT.discard(idempotency_key)

    Thread(target=consume, daemon=True, name=f"rag-thread-job-{job_id[:8]}").start()
    return DispatchReceipt(requested, "thread", f"local:{job_id}", idempotency_key, fallback_reason)


def dispatch(job_id: str, idempotency_key: str, run: Callable[[], None]) -> DispatchReceipt:
    """Dispatch once per idempotency key, with an operable local fallback."""
    status = backend_status()
    requested = status["requested"]
    if status["effective"] == "redis":
        try:
            import redis

            client = redis.Redis.from_url(os.environ["REDIS_URL"])
            message = json.dumps({"job_id": job_id, "idempotency_key": idempotency_key})
            # A production consumer group can consume this shared queue. The
            # application runner still claims the durable job before executing.
            message_id = str(client.lpush(QUEUE_KEY, message))
            return DispatchReceipt(requested, "redis", f"redis:{message_id}", idempotency_key)
        except Exception as error:  # pragma: no cover - connection race
            return _thread_dispatch(job_id, idempotency_key, run, requested=requested, fallback_reason=f"Redis dispatch failed: {error}")
    if status["effective"] == "sqs":
        try:
            import boto3

            client = boto3.client("sqs", endpoint_url=os.getenv("RAG_SQS_ENDPOINT_URL") or None)
            response = client.send_message(
                QueueUrl=os.environ["RAG_SQS_QUEUE_URL"],
                MessageBody=json.dumps({"job_id": job_id, "idempotency_key": idempotency_key}),
                MessageDeduplicationId=idempotency_key,
                MessageGroupId=os.getenv("RAG_SQS_MESSAGE_GROUP_ID", "rag-portal"),
            )
            return DispatchReceipt(requested, "sqs", f"sqs:{response.get('MessageId', job_id)}", idempotency_key)
        except Exception as error:  # pragma: no cover - connection race
            return _thread_dispatch(job_id, idempotency_key, run, requested=requested, fallback_reason=f"SQS dispatch failed: {error}")
    return _thread_dispatch(job_id, idempotency_key, run, requested=requested, fallback_reason=None if requested in {"thread", "local"} else status["detail"])


def queue_observability() -> dict:
    """Adapter-level state; durable job counts live in the application store."""
    status = backend_status()
    return {**status, "local_in_flight": len(_LOCAL_IN_FLIGHT), "queue_key": QUEUE_KEY}
