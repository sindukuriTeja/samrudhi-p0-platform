"""Authority guard — architecture section 6.

Permissions are enforced in CODE, not prompts. Every tool call is checked
against the agent's authority_matrix (loaded from YAML) before execution.
"""
import functools
import os
from typing import Any, Callable

import yaml

from config.settings import get_settings


class AuthorityError(Exception):
    """Raised when an agent attempts an action outside its authority matrix."""
    pass


def load_authority_matrix(canonical_id: str) -> dict:
    """Load an agent's authority matrix.

    Priority:
      1. config/authority_matrices/<id>.yaml (if present)
      2. The agent class's AUTHORITY class attribute (registered in agents.base)
      3. {} (deny by default)
    """
    settings = get_settings()
    path = os.path.join(settings.authority_matrix_path, f"{canonical_id}.yaml")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("authority_matrix", {})
    # Fallback: read AUTHORITY from the registered agent class
    try:
        from agents.base import get_agent_class
        cls = get_agent_class(canonical_id)
        if cls is not None and hasattr(cls, "AUTHORITY"):
            return cls.AUTHORITY
    except Exception:
        pass
    return {}


def check_authority(
    canonical_id: str,
    permission: str,
    *,
    extra: dict | None = None,
) -> None:
    """Raise AuthorityError if the agent lacks the given permission.

    permission is a dotted string like 'ops.allocate' or 'gov.approve_certification'.
    """
    matrix = load_authority_matrix(canonical_id)
    allowed = matrix.get(permission, False)
    if not allowed:
        raise AuthorityError(
            f"Agent {canonical_id} is not authorized to perform '{permission}'. "
            f"Authority matrix: {matrix}"
        )


def authority_guard(permission: str) -> Callable:
    """Decorator: enforce a permission on a tool method before it runs.

    Usage:
        class SomeTools:
            def __init__(self, canonical_id):
                self.canonical_id = canonical_id

            @authority_guard("ops.allocate")
            def allocate_work(self, task: str) -> str:
                ...

    The decorated method must accept self as first arg; self.canonical_id is read.
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs) -> Any:
            canonical_id = getattr(self, "canonical_id", None)
            if not canonical_id:
                raise AuthorityError(
                    f"{fn.__name__} called on object without canonical_id attribute"
                )
            check_authority(canonical_id, permission)
            return fn(self, *args, **kwargs)
        return wrapper
    return decorator
