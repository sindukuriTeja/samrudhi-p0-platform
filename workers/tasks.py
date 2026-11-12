"""Celery tasks — the unit of work dispatched by FastAPI to workers.

Each agent's runnable logic is wrapped as a task here. The task body
imports the agent module lazily so the worker only loads what it runs.

Telemetry (execution_log): the real start and end time, wall-clock latency, the model's
prompt/response tokens and model time (collected from backend.core.llm while the agent runs),
and the TRUE status: a run whose model was unavailable, or whose agent reported a failure, is
logged as failed — never as completed.
"""
from celery import shared_task
from datetime import datetime, timezone
import uuid

MODEL_UNAVAILABLE = "[MODEL UNAVAILABLE]"
MODEL_UNAVAILABLE_ERROR = ("Model unavailable: the local model (Ollama) is not running or did not answer in time, "
                           "so nothing was produced for this step.")


def _run_async(coro):
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def classify(result, output: str) -> tuple[str, str | None]:
    """(status, error) for an agent result: failed when the agent or the model failed."""
    agent_status = getattr(result, "status", "completed") if not isinstance(result, str) else "completed"
    text = (output or "").strip()
    if text.startswith(MODEL_UNAVAILABLE):
        return "failed", MODEL_UNAVAILABLE_ERROR
    if agent_status == "failed":
        return "failed", text[:500] or "The agent reported a failure."
    if agent_status == "escalated":
        return "escalated", None
    if not text:
        return "failed", "The agent finished but returned no result."
    return "completed", None


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
    from backend.core.llm import start_usage, stop_usage, usage_summary
    from backend.models import ExecutionLog
    from backend.database import async_session_maker
    import time

    execution_id = f"exec-{uuid.uuid4().hex[:12]}"
    trace_id = uuid.uuid4().hex[:12]
    started_at = datetime.now(timezone.utc)
    started = time.monotonic()

    async def _log(status, *, error=None, tokens=0, usage=None, raw=None, tools=None):
        async with async_session_maker() as s:
            s.add(ExecutionLog(
                execution_id=execution_id,
                agent_id=canonical_id,
                workflow_id=workflow_id,
                task=task_text,
                tenant_id=tenant_id,
                status=status,
                tokens_used=tokens,
                prompt_tokens=(usage or {}).get("prompt_tokens", 0),
                response_tokens=(usage or {}).get("response_tokens", 0),
                latency_s=round(time.monotonic() - started, 2),
                tools_called=list(tools or []),
                started_at=started_at,
                ended_at=datetime.now(timezone.utc),
                error=error,
                trace_id=trace_id,
                raw_result=raw,
            ))
            await s.commit()

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

    calls, token = start_usage()
    try:
        result = agent_mod.run(task_text, **kwargs)
    except Exception as e:
        stop_usage(token)
        usage = usage_summary(calls)
        _run_async(_log("failed", error=str(e), usage=usage, raw={"telemetry": usage}))
        return {
            "execution_id": execution_id,
            "status": "failed",
            "error": str(e),
            "latency_s": round(time.monotonic() - started, 2),
        }
    stop_usage(token)

    latency = round(time.monotonic() - started, 2)
    usage = usage_summary(calls)
    output = getattr(result, "text", str(result)) if not isinstance(result, str) else result
    tokens = getattr(result, "tokens_used", 0) or (usage["prompt_tokens"] + usage["response_tokens"])
    status, error = classify(result, output)
    raw = {"output": output, "telemetry": usage, "agent_status": getattr(result, "status", None)}
    _run_async(_log(status, error=error, tokens=tokens, usage=usage, raw=raw,
                    tools=getattr(result, "tools_called", None)))

    out = {
        "execution_id": execution_id,
        # an escalation is a finished run whose text explains the escalation
        "status": "completed" if status == "escalated" else status,
        "output": output,
        "latency_s": latency,
        "tokens_used": tokens,
        "telemetry": usage,
    }
    if error:
        out["error"] = error
    return out
