"""Run the whole Control Room locally with one command.

    python -m scripts.run_all            (from the project root, inside the venv)
    python -m scripts.run_all --port 8000 --no-worker

Steps:
  1. Load .env into the environment (existing variables win). If no database is
     configured, use a local SQLite file (samrudhi_local.db).
  2. Make sure Redis is up: if it is not reachable and Docker is available,
     start the project's redis service (docker compose up -d redis).
  3. Apply database migrations (alembic upgrade head) — additive only.
  4. Seed the agent registry from agents/ (idempotent; never activates agents).
  5. Start a Celery worker (when Redis is up). Without Redis the project runner
     executes the same Celery task in a local process instead.
  6. Serve the API + new UI (/) + previous UI (/legacy) with uvicorn.
Ctrl+C stops everything this script started (Redis keeps running in Docker).
"""
import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def log(msg: str) -> None:
    print(f"[run_all] {msg}", flush=True)


def load_env() -> None:
    env_file = ROOT / ".env"
    if env_file.exists():
        try:
            from dotenv import dotenv_values
            for k, v in dotenv_values(env_file).items():
                if v is not None and k not in os.environ:
                    os.environ[k] = v
        except Exception as e:
            log(f"could not read .env: {e}")
    if "DATABASE_URL" not in os.environ and "POSTGRES_HOST" not in os.environ:
        db = (ROOT / "samrudhi_local.db").as_posix()
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db}"
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ["PYTHONPATH"] = str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")


def redis_up() -> bool:
    u = urlparse(os.environ["REDIS_URL"])
    try:
        with socket.create_connection((u.hostname or "localhost", u.port or 6379), timeout=1.5) as s:
            s.sendall(b"PING\r\n")
            return s.recv(16).startswith(b"+PONG")
    except OSError:
        return False


def ensure_redis() -> bool:
    if redis_up():
        log("Redis is up.")
        return True
    if shutil.which("docker"):
        log("Redis is not reachable; starting it with Docker (docker compose up -d redis)…")
        r = subprocess.run(["docker", "compose", "up", "-d", "redis"], cwd=ROOT)
        if r.returncode == 0:
            for _ in range(20):
                if redis_up():
                    log("Redis is up.")
                    return True
                time.sleep(1)
        log("Docker could not start Redis (is Docker Desktop running?).")
    log("Continuing without Redis: live updates fall back to polling and agent steps run in a local process.")
    return False


def run(cmd: list[str], what: str) -> None:
    log(what)
    r = subprocess.run(cmd, cwd=ROOT, env=os.environ.copy())
    if r.returncode != 0:
        log(f"FAILED: {what}")
        sys.exit(r.returncode)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-worker", action="store_true", help="do not start a Celery worker")
    args = ap.parse_args()

    load_env()
    log(f"Database: {os.environ.get('DATABASE_URL', 'PostgreSQL from POSTGRES_* settings')}")
    have_redis = ensure_redis()
    run([PY, "-m", "alembic", "upgrade", "head"], "Applying database migrations…")
    run([PY, "-m", "scripts.seed_agents"], "Seeding the agent registry (idempotent)…")

    procs: list[subprocess.Popen] = []
    if have_redis and not args.no_worker:
        log("Starting the Celery worker…")
        procs.append(subprocess.Popen(
            [PY, "-m", "celery", "-A", "workers.celery_app", "worker", "--pool=solo", "--loglevel=warning"],
            cwd=ROOT, env=os.environ.copy()))
    log(f"Control Room:  http://localhost:{args.port}/        (previous UI: /legacy/, API docs: /docs)")
    try:
        subprocess.run([PY, "-m", "uvicorn", "backend.app_full:app", "--host", args.host, "--port", str(args.port)],
                       cwd=ROOT, env=os.environ.copy())
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            p.terminate()
            try:
                p.wait(timeout=10)
            except Exception:
                p.kill()
        log("Stopped.")


if __name__ == "__main__":
    main()
