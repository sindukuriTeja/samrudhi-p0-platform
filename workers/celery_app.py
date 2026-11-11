"""Celery worker configuration.

All agent tasks run through this worker pool. LLM calls are serialized
inside the worker via the shared lock in backend.core.llm.
"""
import os
from celery import Celery

from config.settings import get_settings

settings = get_settings()

# Redis is the broker AND result backend
broker_url = settings.redis_url
result_backend = settings.redis_url

celery_app = Celery(
    "samrudhi",
    broker=broker_url,
    backend=result_backend,
    include=["workers.tasks"],
)

# Serialize LLM calls: one task at a time touching the model.
# In practice the lock in backend.core.llm handles this, but we also
# limit concurrency at the worker level for memory safety.
celery_app.conf.update(
    worker_concurrency=2,  # keep low — 7B model is memory-heavy
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
