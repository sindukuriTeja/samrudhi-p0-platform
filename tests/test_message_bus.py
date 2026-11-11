"""Tests for the message bus (durable log).

Runs against SQLite (JSON type is portable). Postgres-specific JSONB behavior
is validated separately in integration tests.
"""
import pytest
from backend.core.message_bus import MessageBus, BusEnvelope


@pytest.mark.asyncio
async def test_publish_writes_durable_log():
    """Publishing an event writes to bus_events (source of truth)."""
    bus = MessageBus(redis_client=None)  # no Redis — durable log only
    env = BusEnvelope(
        event_type="agent.activated",
        source_agent="SAM-AG-158",
        target_agent="all",
        payload={"agent_id": "SAM-AG-001", "status": "active"},
        tenant_id="DEMO-HEALTHCARE-01",
        severity="info",
    )
    event_id = await bus.publish(env)
    assert event_id == env.event_id

    # Query it back
    events = await bus.query_events(source_agent="SAM-AG-158", limit=10)
    assert len(events) >= 1
    assert events[0]["event_id"] == env.event_id
    assert events[0]["event_type"] == "agent.activated"


@pytest.mark.asyncio
async def test_publish_severity_s1_flagged():
    """S1 events are queryable by severity."""
    bus = MessageBus(redis_client=None)
    env = BusEnvelope(
        event_type="incident.raised",
        source_agent="SAM-AG-010",
        target_agent="SAM-AG-001",
        payload={"incident_id": "INC-001"},
        tenant_id="DEMO-HEALTHCARE-01",
        severity="S1",
    )
    await bus.publish(env)
    events = await bus.query_events(severity="S1", limit=10)
    assert any(e["event_id"] == env.event_id for e in events)
