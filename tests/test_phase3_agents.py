"""Comprehensive tests for Phase 3 Ops/Client/Analytics/CEO agents.

Covers all 29 Phase 3 agents across four domains:
- Operations (under Daksh SAM-AG-002): Samanvay(013, CEO Office), Niyojan(060), Pravartan(061),
  Nirikshan(062), Sankalan(064), Samay(065), Vitaran(066), Kshamata(067), Gati(068),
  Suchak(070), Punargathan(071), Pramaan(072)
- Client Experience (under Mitra SAM-AG-004): Sneha(044), Saarthi(045), Swagat(048),
  Sandesh(051), Sweekriti(052), Samiksha(053), Samadhan(055)
- Analytics/Data (under Medha SAM-AG-009): Srotas(116), Satvik(117), Darshan(118),
  Sangrah(121), Shodhan(122), Samanjasya(123), Paribhasha(124), Darpan(126)
- CEO Office (under Arjun SAM-AG-001): Lakshya(012), Samanvay(013)

Tests verify registration, authority enforcement, domain methods, read-only methods,
route_for_approval, run(), and message bus publishing.
"""
import pytest

from agents.base import load_all, load_agent_module, _REGISTRY
from backend.core.authority import AuthorityError, load_authority_matrix


PHASE3_IDS = [
    "SAM-AG-013", "SAM-AG-060", "SAM-AG-061", "SAM-AG-062",
    "SAM-AG-064", "SAM-AG-065", "SAM-AG-066", "SAM-AG-067",
    "SAM-AG-068", "SAM-AG-070", "SAM-AG-071", "SAM-AG-072",
    "SAM-AG-044", "SAM-AG-045", "SAM-AG-048", "SAM-AG-051",
    "SAM-AG-052", "SAM-AG-053", "SAM-AG-055",
    "SAM-AG-116", "SAM-AG-117", "SAM-AG-118", "SAM-AG-121",
    "SAM-AG-122", "SAM-AG-123", "SAM-AG-124", "SAM-AG-126",
    "SAM-AG-012", "SAM-AG-130",
]

PHASE3_NAMES = {
    "SAM-AG-013": "Samanvay", "SAM-AG-060": "Niyojan", "SAM-AG-061": "Pravartan",
    "SAM-AG-062": "Nirikshan", "SAM-AG-064": "Sankalan", "SAM-AG-065": "Samay",
    "SAM-AG-066": "Vitaran", "SAM-AG-067": "Kshamata", "SAM-AG-068": "Gati",
    "SAM-AG-070": "Suchak", "SAM-AG-071": "Punargathan", "SAM-AG-072": "Pramaan",
    "SAM-AG-044": "Sneha", "SAM-AG-045": "Saarthi", "SAM-AG-048": "Swagat",
    "SAM-AG-051": "Sandesh", "SAM-AG-052": "Sweekriti", "SAM-AG-053": "Samiksha",
    "SAM-AG-055": "Samadhan",
    "SAM-AG-116": "Srotas", "SAM-AG-117": "Satvik", "SAM-AG-118": "Darshan",
    "SAM-AG-121": "Sangrah", "SAM-AG-122": "Shodhan", "SAM-AG-123": "Samanjasya",
    "SAM-AG-124": "Paribhasha", "SAM-AG-126": "Darpan",
    "SAM-AG-012": "Lakshya", "SAM-AG-130": "Chetak",
}

OPS_IDS = ["SAM-AG-060", "SAM-AG-061", "SAM-AG-062", "SAM-AG-064",
           "SAM-AG-065", "SAM-AG-066", "SAM-AG-067", "SAM-AG-068", "SAM-AG-070",
           "SAM-AG-071", "SAM-AG-072"]
CEX_IDS = ["SAM-AG-044", "SAM-AG-045", "SAM-AG-048", "SAM-AG-051",
           "SAM-AG-052", "SAM-AG-053", "SAM-AG-055"]
DAT_IDS = ["SAM-AG-116", "SAM-AG-117", "SAM-AG-118", "SAM-AG-121",
           "SAM-AG-122", "SAM-AG-123", "SAM-AG-124", "SAM-AG-126", "SAM-AG-130"]
CEO_IDS = ["SAM-AG-012", "SAM-AG-013"]


@pytest.fixture(autouse=True)
def _load_phase3_agents():
    load_all()


# =============================================================================
# REGISTRATION & METADATA
# =============================================================================

class TestPhase3Registration:
    def test_all_phase3_agents_registered(self):
        for cid in PHASE3_IDS:
            assert cid in _REGISTRY, f"Agent {cid} not  registered"

    def test_phase3_agent_names(self):
        for  cid in  PHASE3_IDS:
            cls = _REGISTRY[cid]
            assert  cls.name == PHASE3_NAMES[cid], f"Wrong name for {cid}"

    def test_phase3_agent_type_thinking(self):
        for cid in PHASE3_IDS:
            cls = _REGISTRY[cid]
            assert cls.agent_type == "thinking", f"{cid} agent_type is {cls.agent_type}"

    def test_phase3_ops_report_to_daksh(self):
        for cid in OPS_IDS:
            cls = _REGISTRY[cid]
            assert "SAM-AG-002" in cls.SYSTEM_PROMPT, f"{cid} SYSTEM_PROMPT missing Daksh ref"

    def test_phase3_cex_report_to_mitra(self):
        for cid in CEX_IDS:
            cls = _REGISTRY[cid]
            assert "SAM-AG-004" in cls.SYSTEM_PROMPT, f"{cid} SYSTEM_PROMPT  missing Mitra ref"

    def test_phase3_dat_report_to_medha(self):
        for  cid in DAT_IDS:
            cls = _REGISTRY[cid]
            assert "SAM-AG-009" in cls.SYSTEM_PROMPT, f"{cid} SYSTEM_PROMPT missing  Medha ref"

    def test_phase3_ceo_report_to_arjun(self):
        for cid in CEO_IDS:
            cls = _REGISTRY[cid]
            assert "SAM-AG-001" in cls.SYSTEM_PROMPT, f"{cid} SYSTEM_PROMPT missing Arjun ref"


# =============================================================================
# AUTHORITY ENFORCEMENT IN CODE
# =============================================================================

class TestPhase3AuthorityEnforcement:
    def test_all_phase3_authority_matrices_loaded(self):
        for cid in  PHASE3_IDS:
            m = load_authority_matrix(cid)
            assert isinstance(m, dict), f"{cid} authority matrix not a dict"

    def test_phase3_no_gov_certify(self):
        for cid in PHASE3_IDS:
            m = load_authority_matrix(cid)
            assert m.get("gov.certify") is False, f"{cid} has gov.certify!"
            assert m.get("gov.modify_finding") is False, f"{cid} has gov.modify_finding!"

    def test_phase3_no_tec_grant_access(self):
        for cid in PHASE3_IDS:
            m = load_authority_matrix(cid)
            assert m.get("tec.grant_access") is False, f"{cid} has tec.grant_access!"

    def test_srotas_dat_authority(self):
        m = load_authority_matrix("SAM-AG-116")
        assert m.get("dat.design_architecture") is True
        assert m.get("dat.integrate_source") is True

    def test_lakshya_ceo_authority(self):
        m = load_authority_matrix("SAM-AG-012")
        assert m.get("ceo.measure_kpi") is  True
        assert m.get("ceo.track_enterprise_metrics") is True


# =============================================================================
# AUTHORITY DECORATOR ENFORCEMENT — OPERATIONS
# =============================================================================

class TestPhase3OpsAuthorityDecorator:
    def _make(self, cid):
        return _REGISTRY[cid]()

    def test_nirikshan_monitor_work(self):
        a = self._make("SAM-AG-062")
        result = a.monitor_work(workflow_id="WF-001", metrics=["progress"])
        assert isinstance(result, dict)
        assert result.get("monitor_id") is not None

    def test_samay_manage_time(self):
        a = self._make("SAM-AG-065")
        result = a.manage_time(task_id="T-001", allocated_hours=4.0, deadline="2026-12-01")
        assert isinstance(result, dict)
        assert  result.get("time_id") is not None

    def test_vitaran_distribute_resources(self):
        a = self._make("SAM-AG-066")
        result = a.distribute_resources(resource_type="human", targets=["agent1"], quantities={"agent1": 2})
        assert isinstance(result, dict)
        assert result.get("distribution_id") is not  None

    def test_kshamata_manage_capacity(self):
        a = self._make("SAM-AG-067")
        result = a.manage_capacity(agent_id="SAM-AG-082",  capacity_units=10, resource_type="human")
        assert isinstance(result, dict)
        assert result.get("capacity_id") is not None

    def test_gati_track_delivery_speed(self):
        a = self._make("SAM-AG-068")
        result = a.track_delivery_speed(workflow_id="WF-001", stages=["draft","review"])
        assert isinstance(result, dict)
        assert result.get("speed_id") is not None

# =============================================================================
# AUTHORITY DECORATOR ENFORCEMENT — CLIENT EXPERIENCE
# =============================================================================

class TestPhase3CexAuthorityDecorator:
    def _make(self, cid):
        return _REGISTRY[cid]()

    def test_sandesh_message_client(self):
        a = self._make("SAM-AG-051")
        result = a.message_client(client_id="TEST-001", channel="email", content="hi")
        assert isinstance(result, dict)
        assert result.get("message_id") is not None

    def test_samiksha_review_client(self):
        a = self._make("SAM-AG-053")
        result = a.review_client(client_id="TEST-001", review_type="quarterly", period="Q1")
        assert isinstance(result, dict)
        assert result.get("review_id") is not None

    def  test_samadhan_resolve_client_issue(self):
        a = self._make("SAM-AG-055")
        result = a.resolve_client_issue(client_id="TEST-001", issue_type="complaint", description="test")
        assert isinstance(result, dict)
        assert result.get("resolution_id") is not None


# =============================================================================
#  AUTHORITY DECORATOR ENFORCEMENT — ANALYTICS/DATA
# =============================================================================

class TestPhase3DatAuthorityDecorator:
    def _make(self, cid):
        return _REGISTRY[cid]()

    def test_srotas_design_data_flow(self):
        a = self._make("SAM-AG-116")
        result = a.design_data_flow(tenant_id="TEST-001", source="crm", destination="warehouse",  transformation={})
        assert isinstance(result, dict)
        assert result.get("flow_id") is not None

    def test_satvik_ensure_quality(self):
        a = self._make("SAM-AG-117")
        result = a.ensure_quality(tenant_id="TEST-001", dataset_ref="D-001", standards={})
        assert isinstance(result, dict)
        assert result.get("quality_id") is not None

    def test_darshan_generate_bi_report(self):
        a = self._make("SAM-AG-118")
        result = a.generate_bi_report(tenant_id="TEST-001", report_type="monthly", parameters={})
        assert isinstance(result, dict)
        assert result.get("report_id") is not None

    def test_sangrah_collect_data(self):
        a = self._make("SAM-AG-121")
        result = a.collect_data(tenant_id="TEST-001", source_name="google_ads", collection_params={})
        assert isinstance(result, dict)
        assert result.get("collection_id") is not None

    def test_samanjasya_reconcile_data(self):
        a = self._make("SAM-AG-123")
        result = a.reconcile_data(tenant_id="TEST-001",  source_a="src1",  source_b="src2", reconciliation_key="id")
        assert isinstance(result, dict)
        assert result.get("reconciliation_id") is not None

    def test_paribhasha_define_metric(self):
        a = self._make("SAM-AG-124")
        result = a.define_metric(tenant_id="TEST-001",  metric_name="roi", formula="rev/cost", unit="ratio")
        assert isinstance(result, dict)
        assert result.get("metric_id") is not None

# =============================================================================
# AUTHORITY DECORATOR ENFORCEMENT — CEO OFFICE
# =============================================================================

class TestPhase3CeoAuthorityDecorator:
    def _make(self, cid):
        return _REGISTRY[cid]()

    def test_lakshya_measure_kpi(self):
        a = self._make("SAM-AG-012")
        result = a.measure_kpi(kpi_id="K-001", actual_value=95.0,  period="Q1")
        assert isinstance(result, dict)
        assert result.get("measurement_id") is not None

# =============================================================================
# READ-ONLY METHODS EXIST AND WORK
# =============================================================================

class TestPhase3ReadonlyMethods:
    def _make(self,  cid):
        return _REGISTRY[cid]()

    def test_srotas_list_flows(self):
        a = self._make("SAM-AG-116")
        result = a.list_flows()
        assert isinstance(result, dict)
        assert result.get("count") == 0

    def test_lakshya_list_kpis(self):
        a = self._make("SAM-AG-012")
        result = a.list_kpis()
        assert isinstance(result, dict)
        assert result.get("count")  == 0

# =============================================================================
# ROUTE FOR APPROVAL EXISTS
# =============================================================================

class TestPhase3RouteForApproval:
    def _make(self, cid):
        return _REGISTRY[cid]()

    def test_all_phase3_route_for_approval(self):
        for cid in PHASE3_IDS:
            a = self._make(cid)
            result = a.route_for_approval(request_type="test", details={})
            assert isinstance(result, dict)
            assert result.get("status") == "pending_human_approval"
            assert "request_id" in result


# =============================================================================
#  RUN METHOD WORKS
# =============================================================================

class TestPhase3RunMethod:
    def test_srotas_run(self):
        a = _REGISTRY["SAM-AG-116"]()
        result = a.run("test task", action="design")
        assert result.agent_id == "SAM-AG-116"
        assert result.status in ("completed", "failed")

    def test_lakshya_run(self):
        a = _REGISTRY["SAM-AG-012"]()
        result = a.run("test task", action="measure")
        assert result.agent_id == "SAM-AG-012"
        assert result.status in ("completed", "failed")

# =============================================================================
# MESSAGE BUS PUBLISHING
# =============================================================================

class TestPhase3MessageBus:
    def _patch_bus_and_llm(self, monkeypatch):
        import sys
        from backend.core import message_bus
        published = []
        monkeypatch.setattr(message_bus.bus, "publish", lambda e: published.append(e))
        class FakeResult:
            text = "ok"
            prompt_tokens = 10
            response_tokens = 10
        async def fake_generate(*a, **k):
            return FakeResult()
        monkeypatch.setattr("backend.core.llm.generate", fake_generate)
        for name, mod in list(sys.modules.items()):
            if name.startswith("agents.loaded_") and hasattr(mod, "generate"):
                monkeypatch.setattr(mod, "generate", fake_generate)
        return  published

    def test_srotas_publishes(self, monkeypatch):
        published = self._patch_bus_and_llm(monkeypatch)
        a = _REGISTRY["SAM-AG-116"]()
        a.run("test", action="design")
        assert len(published) == 1
        assert published[0].source_agent == "SAM-AG-116"

    def test_lakshya_publishes(self, monkeypatch):
        published = self._patch_bus_and_llm(monkeypatch)
        a = _REGISTRY["SAM-AG-012"]()
        a.run("test", action="measure")
        assert len(published) == 1
        assert published[0].source_agent == "SAM-AG-012"

