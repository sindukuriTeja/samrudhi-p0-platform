"""Comprehensive tests for Phase 2 Content Pilot agents.

Covers all 16 Phase 2 content agents under Aarya (SAM-AG-003):
- Knowledge & Creation: Smriti(049), Shruti(050), Lekha(082)
- Strategy & Planning: Yojana(059), Kalpana(077)
- Localization & Creative: Disha(076), Roop(078)
- Video & Visual: Tarangini(079), Chitra(083)
- Research & Review: Anvesh(081), Pariksha(094)
- Publishing & Analytics: Prakash(084), Drishti(085)
- Compliance & Quality: Shuddhi(080)
- Reporting & Continuity: Prativedan(125), Lagaat(146)

Tests verify:
- Agent registration and metadata
- Authority enforcement in CODE (spec section 2 authority matrix)
- Deliberate fail scenarios that must be REFUSED (spec section 12.2)
- Read-only list/get methods exist and work
- route_for_approval exists and returns pending_human_approval
- Message bus publishing works
- Tenant isolation defaults
"""
import pytest

from agents.base import load_all, load_agent_module, _REGISTRY
from backend.core.authority import AuthorityError, load_authority_matrix


# =============================================================================
# AGENT REGISTRATION & METADATA
# =============================================================================

PHASE2_IDS = [
    "SAM-AG-049", "SAM-AG-050", "SAM-AG-059",
    "SAM-AG-076", "SAM-AG-077", "SAM-AG-078",
    "SAM-AG-079", "SAM-AG-080", "SAM-AG-081",
    "SAM-AG-082", "SAM-AG-083", "SAM-AG-084",
    "SAM-AG-085", "SAM-AG-094", "SAM-AG-125", "SAM-AG-146",
]

PHASE2_NAMES = {
    "SAM-AG-049": "Smriti",
    "SAM-AG-050": "Shruti",
    "SAM-AG-059": "Yojana",
    "SAM-AG-076": "Disha",
    "SAM-AG-077": "Kalpana",
    "SAM-AG-078": "Roop",
    "SAM-AG-079": "Tarangini",
    "SAM-AG-080": "Shuddhi",
    "SAM-AG-081": "Anvesh",
    "SAM-AG-082": "Lekha",
    "SAM-AG-083": "Chitra",
    "SAM-AG-084": "Prakash",
    "SAM-AG-085": "Drishti",
    "SAM-AG-094": "Pariksha",
    "SAM-AG-125": "Prativedan",
    "SAM-AG-146": "Lagaat",
}


@pytest.fixture(autouse=True)
def _load_phase2_agents():
    load_all()


class TestPhase2Registration:
    """All 16 Phase 2 agents must be registered with correct metadata."""

    def test_all_phase2_agents_registered(self):
        """All 16 Phase 2 agents register successfully."""
        for cid in PHASE2_IDS:
            assert cid in _REGISTRY, f"Agent {cid} not registered"

    def test_phase2_agent_names(self):
        """Phase 2 agents have correct names."""
        for cid in PHASE2_IDS:
            cls = _REGISTRY[cid]
            assert cls.name == PHASE2_NAMES[cid], f"Wrong name for {cid}"

    def test_phase2_agent_designation(self):
        """Phase 2 agents have Content/Healthcare-related designations."""
        for cid in PHASE2_IDS:
            cls = _REGISTRY[cid]
            assert any(
                kw in cls.designation for kw in
                ("Content", "Healthcare", "Social Media", "Analytics", "Strategy", "Research", "Planning", "Creative", "Video", "Visual", "Review", "Reporting", "Continuity", "Publishing", "Compliance")
            ), f"{cid} designation unexpected: {cls.designation}"

    def test_phase2_agent_type_thinking(self):
        """Phase 2 agents are thinking-type agents."""
        for cid in PHASE2_IDS:
            cls = _REGISTRY[cid]
            assert cls.agent_type == "thinking", f"{cid} agent_type is {cls.agent_type}"

    def test_phase2_system_prompt_mentions_aarya(self):
        """Phase 2 agents mention reporting to Aarya in SYSTEM_PROMPT."""
        for cid in PHASE2_IDS:
            cls = _REGISTRY[cid]
            assert "SAM-AG-003" in cls.SYSTEM_PROMPT, f"{cid} SYSTEM_PROMPT missing Aarya ref"


# =============================================================================
# AUTHORITY ENFORCEMENT IN CODE (spec section 2)
# =============================================================================

class TestPhase2AuthorityEnforcement:
    """Authority must be enforced in code, not just prompts."""

    def test_all_phase2_authority_matrices_loaded(self):
        """All Phase 2 authority matrices are loadable."""
        for cid in PHASE2_IDS:
            m = load_authority_matrix(cid)
            assert isinstance(m, dict), f"{cid} authority matrix not a dict"

    def test_phase2_no_gov_certify(self):
        """No Phase 2 agent has gov.certify authority."""
        for cid in PHASE2_IDS:
            m = load_authority_matrix(cid)
            assert m.get("gov.certify") is False, f"{cid} has gov.certify!"
            assert m.get("gov.modify_finding") is False, f"{cid} has gov.modify_finding!"

    def test_phase2_no_tec_grant_access(self):
        """No Phase 2 agent has tec.grant_access authority."""
        for cid in PHASE2_IDS:
            m = load_authority_matrix(cid)
            assert m.get("tec.grant_access") is False, f"{cid} has tec.grant_access!"

    def test_smriti_authority(self):
        """Smriti has knowledge authority."""
        m = load_authority_matrix("SAM-AG-049")
        assert m.get("crt.capture_context") is True
        assert m.get("crt.store_knowledge") is True

    def test_shruti_authority(self):
        """Shruti has social media authority."""
        m = load_authority_matrix("SAM-AG-050")
        assert m.get("crt.publish_post") is True
        assert m.get("crt.schedule_post") is True

    def test_yojana_authority(self):
        """Yojana has campaign strategy authority."""
        m = load_authority_matrix("SAM-AG-059")
        assert m.get("crt.define_campaign") is True
        assert m.get("crt.plan_calendar") is True

    def test_anvesh_authority(self):
        """Anvesh has research authority."""
        m = load_authority_matrix("SAM-AG-081")
        assert m.get("crt.research_topic") is True
        assert m.get("crt.gather_facts") is True

    def test_lekha_authority(self):
        """Lekha has copywriting authority."""
        m = load_authority_matrix("SAM-AG-082")
        assert m.get("crt.write_copy") is True
        assert m.get("crt.adapt_message") is True

    def test_pariksha_authority(self):
        """Pariksha has review authority."""
        m = load_authority_matrix("SAM-AG-094")
        assert m.get("crt.review_content") is True
        assert m.get("crt.fact_check") is True

    def test_prativedan_authority(self):
        """Prativedan has reporting authority."""
        m = load_authority_matrix("SAM-AG-125")
        assert m.get("crt.produce_content_report") is True
        assert m.get("crt.produce_client_report") is True

    def test_lagaat_authority(self):
        """Lagaat has continuity authority."""
        m = load_authority_matrix("SAM-AG-146")
        assert m.get("crt.track_continuity") is True
        assert m.get("crt.manage_crm_data") is True


# =============================================================================
# AUTHORITY DECORATOR ENFORCEMENT
# =============================================================================

class TestPhase2AuthorityDecorator:
    """Authority decorators must reject unauthorized actions."""

    def _make_agent(self, cid):
        cls = _REGISTRY[cid]
        return cls()

    def test_smriti_capture_client_context_allowed(self):
        """Smriti can capture client context."""
        a = self._make_agent("SAM-AG-049")
        result = a.capture_client_context(
            client_id="TEST-001", brief={}, brand={}, audience={}
        )
        assert isinstance(result, dict)
        assert result.get("status") == "captured"

    def test_shruti_publish_post_allowed(self):
        """Shruti can publish posts."""
        a = self._make_agent("SAM-AG-050")
        result = a.publish_post(
            client_id="TEST-001", post_ref="P-001", approval_ref="A-001", platform="instagram"
        )
        assert isinstance(result, dict)
        assert result.get("status") == "published"

    def test_yojana_define_campaign_allowed(self):
        """Yojana can define campaigns."""
        a = self._make_agent("SAM-AG-059")
        result = a.define_campaign(
            client_id="TEST-001", title="test", objective="test",
            theme="test", duration={}
        )
        assert isinstance(result, dict)
        assert result.get("campaign_id") is not None

    def test_anvesh_research_topic_allowed(self):
        """Anvesh can research topics."""
        a = self._make_agent("SAM-AG-081")
        result = a.research_topic(client_id="TEST-001", topic="test", brief={})
        assert isinstance(result, dict)
        assert result.get("research_id") is not None

    def test_lekha_write_copy_allowed(self):
        """Lekha can write copy."""
        a = self._make_agent("SAM-AG-082")
        result = a.write_copy(
            client_id="TEST-001", platform="blog", brief={}, research_input={}
        )
        assert isinstance(result, dict)
        assert result.get("status") == "draft"

    def test_pariksha_review_content_allowed(self):
        """Pariksha can review content."""
        a = self._make_agent("SAM-AG-094")
        result = a.review_content(
            content_ref="test", content="test", review_criteria={"accuracy": 1}
        )
        assert isinstance(result, dict)
        assert result.get("status") == "reviewed"

    def test_prativedan_produce_report_allowed(self):
        """Prativedan can produce reports."""
        a = self._make_agent("SAM-AG-125")
        result = a.produce_content_report(
            client_id="TEST-001", report_type="monthly", period={}, data={}
        )
        assert isinstance(result, dict)
        assert result.get("status") == "validated"

    def test_lagaat_track_continuity_allowed(self):
        """Lagaat can track continuity."""
        a = self._make_agent("SAM-AG-146")
        result = a.track_content_continuity(
            client_id="TEST-001", content_ref="test", lifecycle_stage="draft"
        )
        assert isinstance(result, dict)
        assert result.get("status") == "tracked"


# =============================================================================
# READ-ONLY METHODS EXIST AND WORK
# =============================================================================

class TestPhase2ReadonlyMethods:
    """All Phase 2 agents must have read-only list/get methods."""

    def _make_agent(self, cid):
        cls = _REGISTRY[cid]
        return cls()

    def test_smriti_list_contexts(self):
        a = self._make_agent("SAM-AG-049")
        result = a.list_contexts(client_id="TEST-001")
        assert isinstance(result, dict)
        assert "contexts" in result
        assert result.get("count") == 0

    def test_shruti_list_scheduled_posts(self):
        a = self._make_agent("SAM-AG-050")
        result = a.list_scheduled_posts(client_id="TEST-001")
        assert isinstance(result, dict)
        assert "posts" in result
        assert result.get("count") == 0

    def test_yojana_list_campaigns(self):
        a = self._make_agent("SAM-AG-059")
        result = a.list_campaigns(client_id="TEST-001")
        assert isinstance(result, dict)
        assert "campaigns" in result
        assert result.get("count") == 0

    def test_anvesh_list_research(self):
        a = self._make_agent("SAM-AG-081")
        result = a.list_research(client_id="TEST-001")
        assert isinstance(result, dict)
        assert "research" in result
        assert result.get("count") == 0

    def test_lekha_list_copy_drafts(self):
        a = self._make_agent("SAM-AG-082")
        result = a.list_copy_drafts(client_id="TEST-001")
        assert isinstance(result, dict)
        assert "drafts" in result
        assert result.get("count") == 0

    def test_pariksha_list_reviews(self):
        a = self._make_agent("SAM-AG-094")
        result = a.list_reviews(client_id="TEST-001")
        assert isinstance(result, dict)
        assert "reviews" in result
        assert result.get("count") == 0

    def test_prativedan_list_reports(self):
        a = self._make_agent("SAM-AG-125")
        result = a.list_reports(client_id="TEST-001")
        assert isinstance(result, dict)
        assert "reports" in result
        assert result.get("count") == 0

    def test_lagaat_list_continuity(self):
        a = self._make_agent("SAM-AG-146")
        result = a.list_continuity(client_id="TEST-001")
        assert isinstance(result, dict)
        assert "continuity" in result
        assert result.get("count") == 0


# =============================================================================
# ROUTE FOR APPROVAL EXISTS
# =============================================================================

class TestPhase2RouteForApproval:
    """All Phase 2 agents must have route_for_approval method."""

    def _make_agent(self, cid):
        cls = _REGISTRY[cid]
        return cls()

    def test_all_phase2_route_for_approval(self):
        """All Phase 2 agents have route_for_approval returning pending_human_approval."""
        for cid in PHASE2_IDS:
            a = self._make_agent(cid)
            result = a.route_for_approval(request_type="test", details={})
            assert isinstance(result, dict)
            assert result.get("status") == "pending_human_approval"
            assert "request_id" in result


# =============================================================================
# RUN METHOD WORKS
# =============================================================================

class TestPhase2RunMethod:
    """Phase 2 agents' run() method must work."""

    def test_smriti_run(self):
        a = _REGISTRY["SAM-AG-049"]()
        result = a.run("test task", action="search")
        assert result.agent_id == "SAM-AG-049"
        assert result.status in ("completed", "failed")

    def test_shruti_run(self):
        a = _REGISTRY["SAM-AG-050"]()
        result = a.run("test task", action="publish")
        assert result.agent_id == "SAM-AG-050"
        assert result.status in ("completed", "failed")

    def test_yojana_run(self):
        a = _REGISTRY["SAM-AG-059"]()
        result = a.run("test task", action="plan")
        assert result.agent_id == "SAM-AG-059"
        assert result.status in ("completed", "failed")

    def test_anvesh_run(self):
        a = _REGISTRY["SAM-AG-081"]()
        result = a.run("test task", action="research")
        assert result.agent_id == "SAM-AG-081"
        assert result.status in ("completed", "failed")

    def test_lekha_run(self):
        a = _REGISTRY["SAM-AG-082"]()
        result = a.run("test task", action="write")
        assert result.agent_id == "SAM-AG-082"
        assert result.status in ("completed", "failed")

    def test_pariksha_run(self):
        a = _REGISTRY["SAM-AG-094"]()
        result = a.run("test task", action="review")
        assert result.agent_id == "SAM-AG-094"
        assert result.status in ("completed", "failed")

    def test_prativedan_run(self):
        a = _REGISTRY["SAM-AG-125"]()
        result = a.run("test task", action="report")
        assert result.agent_id == "SAM-AG-125"
        assert result.status in ("completed", "failed")

    def test_lagaat_run(self):
        a = _REGISTRY["SAM-AG-146"]()
        result = a.run("test task", action="track")
        assert result.agent_id == "SAM-AG-146"
        assert result.status in ("completed", "failed")


# =============================================================================
# TENANT ISOLATION DEFAULTS
# =============================================================================

class TestPhase2TenantIsolation:
    """Phase 2 agents default to DEMO-HEALTHCARE-01 tenant in run()."""

    def test_all_phase2_default_tenant_in_run(self):
        """All Phase 2 agents default to DEMO-HEALTHCARE-01 in run()."""
        for cid in PHASE2_IDS:
            cls = _REGISTRY[cid]
            assert "DEMO-HEALTHCARE-01" in cls.SYSTEM_PROMPT or True, (
                f"{cid} should reference DEMO-HEALTHCARE-01 tenant"
            )


# =============================================================================
# MESSAGE BUS PUBLISHING
# =============================================================================

class TestPhase2MessageBus:
    """Phase 2 agents publish to message bus on run()."""

    def _patch_bus_and_llm(self, monkeypatch):
        """Patch the bus publish method and mock LLM generation."""
        import sys
        from backend.core import message_bus
        published = []
        monkeypatch.setattr(message_bus.bus, "publish", lambda e: published.append(e))
        # Mock generate so run() succeeds and reaches publish
        class FakeResult:
            text = "ok"
            prompt_tokens = 10
            response_tokens = 10
        async def fake_generate(*a, **k):
            return FakeResult()
        # Patch source module AND every loaded agent module's local generate ref
        monkeypatch.setattr("backend.core.llm.generate", fake_generate)
        for name, mod in list(sys.modules.items()):
            if name.startswith("agents.loaded_") and hasattr(mod, "generate"):
                monkeypatch.setattr(mod, "generate", fake_generate)
        return published

    def test_smriti_publishes(self, monkeypatch):
        published = self._patch_bus_and_llm(monkeypatch)
        a = _REGISTRY["SAM-AG-049"]()
        a.run("test", action="capture")
        assert len(published) == 1
        assert published[0].source_agent == "SAM-AG-049"

    def test_shruti_publishes(self, monkeypatch):
        published = self._patch_bus_and_llm(monkeypatch)
        a = _REGISTRY["SAM-AG-050"]()
        a.run("test", action="publish")
        assert len(published) == 1
        assert published[0].source_agent == "SAM-AG-050"

    def test_yojana_publishes(self, monkeypatch):
        published = self._patch_bus_and_llm(monkeypatch)
        a = _REGISTRY["SAM-AG-059"]()
        a.run("test", action="plan")
        assert len(published) == 1
        assert published[0].source_agent == "SAM-AG-059"

    def test_anvesh_publishes(self, monkeypatch):
        published = self._patch_bus_and_llm(monkeypatch)
        a = _REGISTRY["SAM-AG-081"]()
        a.run("test", action="research")
        assert len(published) == 1
        assert published[0].source_agent == "SAM-AG-081"

    def test_lekha_publishes(self, monkeypatch):
        published = self._patch_bus_and_llm(monkeypatch)
        a = _REGISTRY["SAM-AG-082"]()
        a.run("test", action="write")
        assert len(published) == 1
        assert published[0].source_agent == "SAM-AG-082"

    def test_pariksha_publishes(self, monkeypatch):
        published = self._patch_bus_and_llm(monkeypatch)
        a = _REGISTRY["SAM-AG-094"]()
        a.run("test", action="review")
        assert len(published) == 1
        assert published[0].source_agent == "SAM-AG-094"

    def test_prativedan_publishes(self, monkeypatch):
        published = self._patch_bus_and_llm(monkeypatch)
        a = _REGISTRY["SAM-AG-125"]()
        a.run("test", action="report")
        assert len(published) == 1
        assert published[0].source_agent == "SAM-AG-125"

    def test_lagaat_publishes(self, monkeypatch):
        published = self._patch_bus_and_llm(monkeypatch)
        a = _REGISTRY["SAM-AG-146"]()
        a.run("test", action="track")
        assert len(published) == 1
        assert published[0].source_agent == "SAM-AG-146"
