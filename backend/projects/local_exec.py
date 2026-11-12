"""Run workers.tasks.run_agent_task once in this process (Celery eager apply).

Used by the project runner when no Celery worker / Redis broker is available.
Reads {"args": [...], "kwargs": {...}} on stdin and prints one result line.
"""
import json
import sys


def main() -> None:
    req = json.loads(sys.stdin.read())
    from workers.celery_app import celery_app  # noqa: F401
    from workers.tasks import run_agent_task

    try:
        result = run_agent_task.apply(args=req["args"], kwargs=req["kwargs"]).get(propagate=False)
        if not isinstance(result, dict):
            result = {"status": "failed", "error": str(result)}
    except Exception as e:
        result = {"status": "failed", "error": str(e)}
    from backend.projects.dispatch import RESULT_MARKER
    sys.stdout.write("\n" + RESULT_MARKER + json.dumps(result, default=str) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
