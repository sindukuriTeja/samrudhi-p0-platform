"""Message bus — architecture section 5.

Durable PostgreSQL log (source of truth) + Redis pub/sub (live delivery only).
Every event MUST be written to bus_events FIRST, then published to Redis.
"""
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import async_session_maker
from backend.models import BusEvent


import contextlib as _contextlib
import contextvars as _contextvars

# While competency tests run, agents' tools must not send real events (alerts, escalations).
_suppressed: _contextvars.ContextVar[bool] = _contextvars.ContextVar("bus_suppressed", default=False)


@_contextlib.contextmanager
def suppress_publishing():
    token = _suppressed.set(True)
    try:
        yield
    finally:
        _suppressed.reset(token)


@dataclass
class BusEnvelope:
    """The exact JSON envelope every bus event uses (architecture section 5.1)."""
    event_type: str
    source_agent: str
    target_agent: str  # canonical_id or "all"
    payload: dict
    tenant_id: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    workflow_id: str | None = None
    execution_id: str | None = None
    evidence_refs: list = field(default_factory=list)
    severity: str = "info"  # info | S1..S4
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)

    def dict(self) -> dict:
        return asdict(self)


class MessageBus:
    """Publish/subscribe over Postgres (durable) + Redis (live)."""

    def __init__(self, redis_client=None):
        self._redis = redis_client  # redis.asyncio.Redis, optional

    async def publish(self, envelope: BusEnvelope) -> str:
        """Write to durable log FIRST, then publish to Redis for live delivery.

        Returns the event_id.
        """
        if _suppressed.get():
            return envelope.event_id  # competency test: nothing is sent or logged
        async with async_session_maker() as session:
            event = BusEvent(
                event_id=envelope.event_id,
                event_type=envelope.event_type,
                source_agent=envelope.source_agent,
                target_agent=envelope.target_agent,
                timestamp=datetime.fromisoformat(
                    envelope.timestamp.replace("Z", "+00:00")
                ) if envelope.timestamp.endswith("Z") else datetime.fromisoformat(
                    envelope.timestamp
                ),
                tenant_id=envelope.tenant_id,
                workflow_id=envelope.workflow_id,
                execution_id=envelope.execution_id,
                payload=envelope.payload,
                evidence_refs=envelope.evidence_refs,
                severity=envelope.severity,
                trace_id=envelope.trace_id,
            )
            session.add(event)
            await session.commit()

        # Live delivery only — never the source of truth
        if self._redis is not None:
            try:
                channel = (
                    f"bus:all"
                    if envelope.target_agent == "all"
                    else f"bus:{envelope.target_agent}"
                )
                await self._redis.publish(channel, envelope.to_json())
            except Exception:
                # Redis down must not lose the event — it's already durably logged
                pass

        return envelope.event_id

    def publish_sync(self, envelope: BusEnvelope) -> str:
        """Synchronous wrapper for publish — for use from sync agent classes.

        Runs the async publish in a dedicated event loop. Safe to call from
        non-async contexts (e.g. agent.run()).
        """
        if _suppressed.get():
            return envelope.event_id  # competency test: nothing is sent or logged
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop = asyncio.new_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        return loop.run_until_complete(self.publish(envelope))

    async def query_events(
        self,
        *,
        event_type: str | None = None,
        source_agent: str | None = None,
        target_agent: str | None = None,
        tenant_id: str | None = None,
        severity: str | None = None,
        trace_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query the durable log (for the website / audit)."""
        async with async_session_maker() as session:
            stmt = select(BusEvent)
            if event_type:
                stmt = stmt.where(BusEvent.event_type == event_type)
            if source_agent:
                stmt = stmt.where(BusEvent.source_agent == source_agent)
            if target_agent:
                stmt = stmt.where(BusEvent.target_agent == target_agent)
            if tenant_id:
                stmt = stmt.where(BusEvent.tenant_id == tenant_id)
            if severity:
                stmt = stmt.where(BusEvent.severity == severity)
            if trace_id:
                stmt = stmt.where(BusEvent.trace_id == trace_id)
            stmt = stmt.order_by(BusEvent.timestamp.desc()).limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            return [
                {
                    "event_id": r.event_id,
                    "event_type": r.event_type,
                    "source_agent": r.source_agent,
                    "target_agent": r.target_agent,
                    "timestamp": r.timestamp.isoformat(),
                    "tenant_id": r.tenant_id,
                    "payload": r.payload,
                    "severity": r.severity,
                    "trace_id": r.trace_id,
                }
                for r in rows
            ]


# Global bus instance (redis injected at startup)
bus = MessageBus()
