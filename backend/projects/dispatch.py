"""Dispatch one agent step through the existing Celery task.

Primary path: workers.tasks.run_agent_task.apply_async -> Celery worker (Redis broker).
Fallback (no Redis or no worker online): the SAME Celery task is executed with
task.apply() in a separate local process (backend.projects.local_exec), so it
still writes its normal execution_log / bus records exactly as today.

This module never calls the model and contains no agent logic.
"""
import asyncio
import json
import os
import subprocess
import sys
import time

from backend.projects.events import redis_alive

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULT_MARKER = "__SAMRUDHI_RESULT__"
LOCAL_REF = "local"

_worker_cache: dict = {"at": 0.0, "ok": False}


def _celery():
    from workers.celery_app import celery_app  # noqa: F401  (binds shared_task to this app)
    from workers.tasks import run_agent_task
    return celery_app, run_agent_task


async def worker_available() -> bool:
    """True when Redis is up and at least one Celery worker answers a ping."""
    now = time.monotonic()
    if now - _worker_cache["at"] < 10:
        return _worker_cache["ok"]
    ok = False
    if await redis_alive():
        try:
            celery_app, _ = _celery()
            replies = await asyncio.wait_for(
                asyncio.to_thread(celery_app.control.ping, timeout=1.0), timeout=5
            )
            ok = bool(replies)
        except Exception:
            ok = False
    _worker_cache.update(at=now, ok=ok)
    return ok


async def dispatch(args: list, kwargs: dict, on_ref) -> dict:
    """Run the agent task; call on_ref(ref) once the dispatch reference is known."""
    if await worker_available():
        _, task = _celery()
        res = await asyncio.to_thread(task.apply_async, args=args, kwargs=kwargs)
        await on_ref(res.id)
        return await wait_celery(res.id)
    await on_ref(LOCAL_REF)
    return await asyncio.to_thread(_run_local, args, kwargs)


INTERRUPTED = ("Interrupted: the backend restarted while this step was running and the task "
               "could not be found again. Press Retry to run it again.")


async def wait_celery(task_id: str, pending_timeout: float | None = None) -> dict:
    """Wait for a Celery task result. pending_timeout: give up if it never leaves PENDING."""
    celery_app, _ = _celery()
    from celery.result import AsyncResult

    res = AsyncResult(task_id, app=celery_app)
    first = started = time.monotonic()
    while True:
        try:
            state = await asyncio.to_thread(lambda: res.state)
        except Exception:
            state = None
        if state in ("SUCCESS", "FAILURE", "REVOKED"):
            break
        if pending_timeout is not None and state in ("PENDING", None) \
                and time.monotonic() - started > pending_timeout:
            # Celery reports a running task as PENDING too (task_track_started is off),
            # so ask the workers whether they still hold it. A solo-pool worker that is
            # busy cannot answer (None): keep waiting, up to the 30-minute step limit.
            known = await task_known(task_id)
            if known is False or time.monotonic() - first > 1800:
                return {"status": "failed", "error": INTERRUPTED}
            started = time.monotonic()
        await asyncio.sleep(1.5)
    try:
        value = await asyncio.to_thread(res.get, timeout=10, propagate=False)
    except Exception as e:  # result backend unreachable
        return {"status": "failed", "error": f"Could not read the task result: {e}"}
    if isinstance(value, dict):
        return value
    return {"status": "failed", "error": str(value)}


async def task_known(task_id: str) -> bool | None:
    """True/False if a worker answered (task held or not); None if no worker answered."""
    try:
        celery_app, _ = _celery()

        def _ids():
            insp = celery_app.control.inspect(timeout=2.0)
            ids, answered = set(), False
            for fn in (insp.active, insp.reserved, insp.scheduled):
                replies = fn()
                if replies:
                    answered = True
                for tasks in (replies or {}).values():
                    for t in tasks or []:
                        ids.add(t.get("id") or (t.get("request") or {}).get("id"))
            return ids if answered else None
        ids = await asyncio.wait_for(asyncio.to_thread(_ids), timeout=15)
        return None if ids is None else task_id in ids
    except Exception:
        return None


async def celery_state(task_id: str) -> str | None:
    """Celery state for a task id, or None if it cannot be read."""
    try:
        celery_app, _ = _celery()
        from celery.result import AsyncResult
        return await asyncio.wait_for(
            asyncio.to_thread(lambda: AsyncResult(task_id, app=celery_app).state), timeout=5
        )
    except Exception:
        return None


def _run_local(args: list, kwargs: dict) -> dict:
    payload = json.dumps({"args": args, "kwargs": kwargs})
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "backend.projects.local_exec"],
            input=payload, capture_output=True, text=True, encoding="utf-8",
            cwd=_ROOT, env=os.environ.copy(), timeout=1800,
        )
    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": "The step took longer than 30 minutes and was stopped."}
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith(RESULT_MARKER):
            try:
                return json.loads(line[len(RESULT_MARKER):])
            except Exception:
                break
    tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["no output"]
    return {"status": "failed", "error": f"The agent process ended without a result ({tail[0][:200]})."}
