"""Fila de jobs (RQ) via Redis."""

from __future__ import annotations

import redis
from rq import Queue

from config import REDIS_URL


def get_redis() -> redis.Redis:
    return redis.from_url(REDIS_URL)


def get_queue(name: str = "default") -> Queue:
    return Queue(name, connection=get_redis())

