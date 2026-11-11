"""Base agent class + registry for all Samrudhi agents.

Every agent (thinking, service-first, role) extends BaseAgent.
Agents live in agents/<folder>/agent.py and are loaded dynamically by canonical_id.
"""
import importlib.util
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from config.settings import get_settings


@dataclass
class AgentResult:
    """Standard return from an agent run."""
    text: str
    agent_id: str
    tokens_used: int = 0
    tools_called: list[str] | None = None
    status: str = "completed"  # completed | failed | escalated


class BaseAgent(ABC):
    """Base for all agents.

    Subclasses implement:
      - canonical_id, name, agent_type (class attrs)
      - run(task, **kwargs) → AgentResult
    """
    canonical_id: str = ""
    name: str = ""
    agent_type: str = "thinking"  # thinking | service-first | role

    def __init__(self, canonical_id: str | None = None):
        if canonical_id:
            self.canonical_id = canonical_id

    @abstractmethod
    def run(self, task: str, **kwargs) -> AgentResult:
        """Execute the agent's core function."""
        ...

    def describe(self) -> dict:
        return {
            "canonical_id": self.canonical_id,
            "name": self.name,
            "agent_type": self.agent_type,
        }


# Registry: canonical_id → agent instance class
_REGISTRY: dict[str, type[BaseAgent]] = {}
_LOADED: set[str] = set()


def register_agent(cls: type[BaseAgent]) -> type[BaseAgent]:
    """Decorator: register an agent class."""
    _REGISTRY[cls.canonical_id] = cls
    return cls


def load_agent_module(canonical_id: str) -> None:
    """Dynamically load the agent module for a canonical_id from agents/<id>_*/.

    Looks for a folder named <canonical_id>_<Name> or <canonical_id>_<Name>_pkg
    containing agent.py (or sutra.py/arjun.py/etc — any .py with a BaseAgent subclass).
    """
    if canonical_id in _LOADED:
        return
    agents_dir = os.path.join(os.path.dirname(__file__))
    settings = get_settings()
    # Search folders starting with the canonical_id
    candidates = [
        d for d in os.listdir(agents_dir)
        if d.startswith(canonical_id) and os.path.isdir(os.path.join(agents_dir, d))
    ]
    for folder in candidates:
        folder_path = os.path.join(agents_dir, folder)
        # Find the main module file (agent.py preferred, else first .py)
        main_file = None
        for name in ["agent.py", "sutra.py", "arjun.py", "satya.py", "niyantrak.py"]:
            if os.path.exists(os.path.join(folder_path, name)):
                main_file = os.path.join(folder_path, name)
                break
        if main_file is None:
            py_files = [f for f in os.listdir(folder_path) if f.endswith(".py") and f != "__init__.py"]
            if py_files:
                main_file = os.path.join(folder_path, py_files[0])
        if main_file is None:
            continue
        module_name = f"agents.loaded_{canonical_id}"
        spec = importlib.util.spec_from_file_location(module_name, main_file)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception:
            # Module failed to load — skip, agent won't be registered
            continue
    _LOADED.add(canonical_id)


def get_agent_class(canonical_id: str) -> type[BaseAgent] | None:
    load_agent_module(canonical_id)
    return _REGISTRY.get(canonical_id)


def get_agent_module(canonical_id: str) -> Any:
    """Return a runnable instance for a canonical_id."""
    cls = get_agent_class(canonical_id)
    if cls is None:
        raise KeyError(f"Agent {canonical_id} not registered")
    return cls()


def list_registered() -> list[str]:
    return sorted(_REGISTRY.keys())


def load_all() -> list[str]:
    """Load all agent modules found in the agents directory.

    Folders are named <canonical_id>_<Name> where canonical_id is SAM-AG-001.
    """
    agents_dir = os.path.dirname(__file__)
    for d in os.listdir(agents_dir):
        full = os.path.join(agents_dir, d)
        if os.path.isdir(full) and not d.startswith("_") and d != "__pycache__":
            # Extract canonical_id: everything before the last underscore segment
            if "_" in d:
                cid = d.rsplit("_", 1)[0]
            else:
                cid = d
            if cid.startswith("SAM-AG-"):
                try:
                    load_agent_module(cid)
                except Exception:
                    pass
    return list_registered()
