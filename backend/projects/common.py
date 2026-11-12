"""Small shared helpers for the project flow."""
import uuid
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; everything is stored as UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def iso(dt: datetime | None) -> str | None:
    dt = aware(dt)
    return dt.isoformat().replace("+00:00", "Z") if dt else None


def seconds_between(a: datetime | None, b: datetime | None) -> int | None:
    a, b = aware(a), aware(b)
    if not a or not b:
        return None
    return max(0, int((b - a).total_seconds()))


def new_project_id() -> str:
    return f"PRJ-{uuid.uuid4().hex[:8].upper()}"


def new_approval_id() -> str:
    # approvals.request_id is VARCHAR(20)
    return f"APR-{uuid.uuid4().hex[:12].upper()}"


# Lifecycle states in which an agent is deployed and allowed to run.
RUNNABLE_STATES = ("active", "monitored")
OPEN_PROJECT_STATES = ("running", "paused", "needs_attention")
ENDED_PROJECT_STATES = ("completed", "stopped")
