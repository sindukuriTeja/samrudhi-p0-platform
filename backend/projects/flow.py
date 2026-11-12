"""Load project flows from config/project_flows.yaml and answer questions about them."""
import inspect
import os
import re
from functools import lru_cache

import yaml

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FLOWS_PATH = os.path.join(_ROOT, "config", "project_flows.yaml")

BLOCKS = {
    1: "Start and check", 2: "Kick-off", 3: "Understand the client", 4: "Plan the delivery",
    5: "Decide the content", 6: "Make the content", 7: "Check the content",
    8: "Send and publish", 9: "Measure and report", 10: "Close",
}


@lru_cache
def _load() -> dict:
    with open(FLOWS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def default_flow_key() -> str:
    return _load().get("default_flow", "documented_chain")


def get_flow(key: str | None = None) -> dict:
    data = _load()
    key = key or default_flow_key()
    flow = (data.get("flows") or {}).get(key)
    if flow is None:
        # Projects created with an earlier flow keep working against the current one;
        # their old step keys simply have no definition here.
        fallback = default_flow_key()
        flow = (data.get("flows") or {}).get(fallback)
        if flow is None:
            raise KeyError(f"Unknown project flow: {key}")
        return {"key": fallback, "legacy_key": key, **flow}
    return {"key": key, **flow}


def step_def(flow: dict, step_key: str) -> dict | None:
    for s in flow["steps"]:
        if s["key"] == step_key:
            return {"mode": "think", **s}
    rework = flow.get("rework")
    if rework and rework.get("key") == step_key:
        return {"mode": "tool", "block": 7, **rework}
    return None


def step_keys(flow: dict) -> list[str]:
    return [s["key"] for s in flow["steps"]]


def running_steps(flow: dict) -> list[dict]:
    """Steps whose agent actually runs (not 'skip'), plus the rework coordinator."""
    out = [step_def(flow, s["key"]) for s in flow["steps"] if s.get("mode", "think") != "skip"]
    if flow.get("rework"):
        out.append(step_def(flow, flow["rework"]["key"]))
    return out


def required_agents(flow: dict) -> list[str]:
    seen: list[str] = []
    for s in running_steps(flow):
        if s["agent"] not in seen:
            seen.append(s["agent"])
    return seen


def tool_permission(agent_id: str, method: str) -> str | None:
    """The permission an agent tool's @authority_guard requires (read from the agent's own code)."""
    from agents.base import get_agent_class
    cls = get_agent_class(agent_id)
    if cls is None:
        return None
    tools = getattr(cls, "TOOLS", None)
    if tools and method in tools:
        return tools[method]
    try:
        src = inspect.getsource(cls)
    except (OSError, TypeError):
        return None
    m = re.search(r'@authority_guard\("([^"]+)"\)\s*\n\s*def ' + re.escape(method) + r"\(", src)
    return m.group(1) if m else None


def step_permission(step: dict, round_no: int = 1) -> str | None:
    if step.get("mode") == "tool":
        return tool_permission(step["agent"], step["method"])
    if round_no > 1 and step.get("revise_permission"):
        return step["revise_permission"]
    return step.get("permission")


def chain_permissions(flow: dict) -> list[list[str]]:
    pairs = []
    for s in running_steps(flow):
        perm = step_permission(s)
        if perm:
            pairs.append([s["agent"], perm])
    return pairs


def checks_between(flow: dict, start_key: str, end_key: str) -> list[str]:
    keys = step_keys(flow)
    i, j = keys.index(start_key), keys.index(end_key)
    return keys[i:j + 1]
