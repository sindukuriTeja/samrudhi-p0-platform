"""Load project flows from config/project_flows.yaml."""
import os
from functools import lru_cache

import yaml

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FLOWS_PATH = os.path.join(_ROOT, "config", "project_flows.yaml")


@lru_cache
def _load() -> dict:
    with open(FLOWS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def default_flow_key() -> str:
    return _load().get("default_flow", "content_production")


def get_flow(key: str | None = None) -> dict:
    data = _load()
    key = key or default_flow_key()
    flow = (data.get("flows") or {}).get(key)
    if flow is None:
        raise KeyError(f"Unknown project flow: {key}")
    return {"key": key, **flow}


def step_def(flow: dict, step_key: str) -> dict | None:
    return next((s for s in flow["steps"] if s["key"] == step_key), None)


def required_agents(flow: dict) -> list[str]:
    seen: list[str] = []
    for s in flow["steps"]:
        if s["agent"] not in seen:
            seen.append(s["agent"])
    return seen


def revise_permission_for(flow: dict, step_key: str) -> str | None:
    """Permission to use when step_key runs as a revision round after a human decision."""
    for s in flow["steps"]:
        appr = s.get("approval") or {}
        if appr.get("revise_step") == step_key and appr.get("revise_permission"):
            return appr["revise_permission"]
    return None
