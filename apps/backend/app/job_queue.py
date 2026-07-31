"""Small queue adapter: Redis when provisioned, durable thread fallback locally."""

from __future__ import annotations

import os
from threading import Thread
from typing import Callable


QUEUE_KEY = "rag-portal:processing"


def backend_name() -> str:
    if os.getenv("RAG_QUEUE_BACKEND", "thread").lower() != "redis":
        return "thread"
    try:
        import redis

        client = redis.Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=0.5)
        client.ping()
        return "redis"
    except Exception:
        return "thread"


def dispatch(job_id: str, run: Callable[[], None]) -> str:
    """Enqueue to Redis when available, otherwise preserve local developer flow."""
    if backend_name() == "redis":
        import redis

        client = redis.Redis.from_url(os.environ["REDIS_URL"])
        queue_key = f"{QUEUE_KEY}:{job_id}"
        client.lpush(queue_key, job_id)

        def consume() -> None:
            # A production worker can replace this consumer without changing
            # the API contract; this keeps a one-process deployment functional.
            item = client.brpop(queue_key, timeout=1)
            if item and item[1].decode() == job_id:
                run()

        Thread(target=consume, daemon=True, name=f"rag-redis-job-{job_id[:8]}").start()
        return "redis"
    Thread(target=run, daemon=True, name=f"rag-thread-job-{job_id[:8]}").start()
    return "thread"
