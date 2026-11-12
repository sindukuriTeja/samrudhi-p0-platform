"""Celery tasks — the unit of work dispatched by FastAPI to workers.

Each agent's runnable logic is wrapped as a task here. The task body
imports the agent module lazily so the worker only loads what it runs.
"""
from celery import shared_task
from datetime import datetime, timezone
import uuid


@shared_task(bind=True, max_retries=2)
def run_agent_task(
    self,
    canonical_id: str,
    task_text: str,
    tenant_id: str,
    workflow_id: str | None = None,
    **kwargs,
) -> dict:
    """Dispatch an agent's run.

    Imports the agent module lazily, runs it, logs telemetry.
    Returns the agent's output dict.
    """
    from backend.core.llm import generate, check_ollama_health
    from backend.models import ExecutionLog
    from backend.database import async_session_maker
    from sqlalchemy import select
    import time

    execution_id = f"exec-{uuid.uuid4().hex[:12]}"
    trace_id = uuid.uuid4().hex[:12]
    started = time.monotonic()

    # Lazy import the agent registry
    try:
        from agents.base import get_agent_module
        agent_mod = get_agent_module(canonical_id)
    except Exception as e:
        return {
            "execution_id": execution_id,
            "status": "failed",
            "error": f"Agent module not found: {e}",
        }

    # Run the agent
    try:
        result = agent_mod.run(task_text, **kwargs)
        latency = round(time.monotonic() - started, 2)
        tokens = getattr(result, "tokens_used", 0) if hasattr(result, "tokens_used") else 0
        output = getattr(result, "text", str(result)) if not isinstance(result, str) else result

        # Log telemetry
        async def _log():
            async with async_session_maker() as s:
                s.add(ExecutionLog(
                    execution_id=execution_id,
                    agent_id=canonical_id,
                    workflow_id=workflow_id,
                    task=task_text,
                    tenant_id=tenant_id,
                    status="completed",
                    tokens_used=tokens,
                    started_at=datetime.now(timezone.utc),
                    ended_at=datetime.now(timezone.utc),
                    trace_id=trace_id,
                    raw_result={"output": output} if isinstance(output, str) else output,
                ))
                await s.commit()

        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        loop.run_until_complete(_log())

        return {
            "execution_id": execution_id,
            "status": "completed",
            "output": output,
            "latency_s": latency,
            "tokens_used": tokens,
        }
    except Exception as e:
        latency = round(time.monotonic() - started, 2)
        async def _log_err():
            async with async_session_maker() as s:
                s.add(ExecutionLog(
                    execution_id=execution_id,
                    agent_id=canonical_id,
                    workflow_id=workflow_id,
                    task=task_text,
                    tenant_id=tenant_id,
                    status="failed",
                    started_at=datetime.now(timezone.utc),
                    ended_at=datetime.now(timezone.utc),
                    error=str(e),
                    trace_id=trace_id,
                ))
                await s.commit()

        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        loop.run_until_complete(_log_err())

        return {
            "execution_id": execution_id,
            "status": "failed",
            "error": str(e),
            "latency_s": latency,
        }
