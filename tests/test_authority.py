"""Tests for the authority guard."""
import os
import pytest
from backend.core.authority import (
    AuthorityError, check_authority, authority_guard, load_authority_matrix,
)


@pytest.fixture
def auth_matrix_dir(tmp_path, monkeypatch):
    """Create a temp authority matrix dir with a sample agent file."""
    from config.settings import get_settings
    matrix_dir = tmp_path / "authority_matrices"
    matrix_dir.mkdir()
    (matrix_dir / "SAM-AG-002.yaml").write_text(
        "agent_id: SAM-AG-002\n"
        "authority_matrix:\n"
        "  ops.allocate: true\n"
        "  ops.escalate: true\n"
        "  ops.change_commercial: false\n"
    )
    monkeypatch.setenv("AUTHORITY_MATRIX_PATH", str(matrix_dir))
    # Clear settings cache so it picks up the new path
    from config import settings as settings_mod
    settings_mod.get_settings.cache_clear()
    yield matrix_dir
    settings_mod.get_settings.cache_clear()


def test_check_authority_allowed(auth_matrix_dir):
    """An allowed permission passes."""
    check_authority("SAM-AG-002", "ops.allocate")  # no exception


def test_check_authority_denied(auth_matrix_dir):
    """A denied permission raises AuthorityError."""
    with pytest.raises(AuthorityError, match="not authorized"):
        check_authority("SAM-AG-002", "ops.change_commercial")


def test_check_authority_unknown_agent(auth_matrix_dir):
    """An agent with no matrix file is denied by default."""
    with pytest.raises(AuthorityError):
        check_authority("SAM-AG-999", "ops.allocate")


def test_authority_guard_decorator(auth_matrix_dir):
    """The decorator enforces permission on a method."""
    class FakeTools:
        canonical_id = "SAM-AG-002"

        @authority_guard("ops.allocate")
        def allocate(self, task: str) -> str:
            return f"allocated: {task}"

        @authority_guard("ops.change_commercial")
        def change_commercial(self) -> str:
            return "should not reach"

    tools = FakeTools()
    assert tools.allocate("build campaign") == "allocated: build campaign"
    with pytest.raises(AuthorityError):
        tools.change_commercial()
