"""Real information: client knowledge store, source library, fetching and fact verification."""
import socket
import uuid

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from agents.base import get_agent_module
from backend.core import knowledge as kn
from backend.core.auth import create_access_token
from backend.routes import knowledge as K

PAGE = """<html><head><title>Diabetes fact sheet</title><script>var x = 'About 9 in 10 cats';</script></head>
<body><nav>Home | Topics | Contact</nav><h1>Diabetes</h1>
<p>About 1 in 10 adults worldwide lives with diabetes. Many people with type 2 diabetes have no symptoms for
years, so a simple blood sugar test is the only way to know.</p>
<p>Common signs include feeling very thirsty, passing urine often, tiredness and blurred vision.
Healthy food, regular activity and not smoking lower the risk of type 2 diabetes.</p>
<footer>Copyright notice</footer></body></html>"""

FOUNDER = {"username": "vikram", "role": "founder"}
ASSURANCE = {"username": "satya_human", "role": "assurance_lead"}
CX = {"username": "divya", "role": "client_experience_lead"}


def public_dns(monkeypatch, ip="93.184.216.34"):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", (ip, 443))])


# ---------------------------------------------------------------- text, retrieval, verification
def test_extract_text_drops_scripts_navigation_and_footer():
    title, text = kn.extract_text(PAGE)
    assert title == "Diabetes fact sheet"
    assert "1 in 10 adults" in text and "cats" not in text and "Contact" not in text and "Copyright" not in text


def test_retrieve_returns_matching_passages_within_budget():
    _, text = kn.extract_text(PAGE)
    sources = [{"id": "SRC-AAA111", "title": "Diabetes fact sheet", "publisher": "WHO", "url": "https://www.who.int/x",
                "topics": ["diabetes"], "text": text},
               {"id": "SRC-BBB222", "title": "Hand washing", "publisher": "X", "url": "https://x", "topics": [],
                "text": "Wash your hands with soap for twenty seconds before eating and after the toilet."}]
    lib = kn.retrieve("World Diabetes Day posts: early signs of type 2 diabetes and screening", sources)
    assert [x["source_id"] for x in lib] == ["SRC-AAA111"]
    assert lib[0]["passages"][0]["passage_id"].startswith("SRC-AAA111#")
    assert sum(len(p["text"]) for x in lib for p in x["passages"]) <= kn.config()["retrieval"]["max_total_chars"]
    assert kn.retrieve("", sources) == []


def _lib():
    _, text = kn.extract_text(PAGE)
    return {"SRC-AAA111": {"id": "SRC-AAA111", "title": "Diabetes fact sheet", "publisher": "WHO",
                           "url": "https://www.who.int/diabetes", "text": text}}


def test_fact_is_verified_only_with_a_real_quote_and_matching_figures():
    lib = _lib()
    ok = kn.verify_fact({"fact": "About 1 in 10 adults lives with diabetes.", "source_id": "SRC-AAA111#1",
                         "quote": "About 1 in 10 adults worldwide lives with diabetes."}, lib)
    assert ok["verified"] and ok["url"] == "https://www.who.int/diabetes" and ok["publisher"] == "WHO"
    wrong_figure = kn.verify_fact({"fact": "About 1 in 5 adults lives with diabetes.", "source_id": "SRC-AAA111",
                                   "quote": "About 1 in 10 adults worldwide lives with diabetes."}, lib)
    assert not wrong_figure["verified"] and "5" in wrong_figure["reason"]
    invented = kn.verify_fact({"fact": "Diabetes can be cured with diet.", "source_id": "SRC-AAA111",
                               "quote": "Diabetes can be fully cured with the right diet."}, lib)
    assert not invented["verified"] and invented["reason"] == "the quote was not found in the source"
    unknown = kn.verify_fact({"fact": "x", "source_id": "SRC-ZZZ999", "quote": "About 1 in 10 adults worldwide"}, lib)
    assert not unknown["verified"] and unknown["url"] is None
    mismatch = kn.verify_fact({"fact": "Smoking causes blurred vision in children.", "source_id": "SRC-AAA111",
                               "quote": "Common signs include feeling very thirsty, passing urine often"}, lib)
    assert not mismatch["verified"]
    # small wording differences in the quote are tolerated, a short fragment is not
    near = kn.verify_fact({"fact": "Many people with type 2 diabetes have no symptoms for years.",
                           "source_id": "SRC-AAA111",
                           "quote": "many people with type 2 diabetes have no symptoms for many years"}, lib)
    assert near["verified"]
    short = kn.verify_fact({"fact": "Diabetes is common.", "source_id": "SRC-AAA111", "quote": "with diabetes"}, lib)
    assert not short["verified"]


def test_anvesh_verifies_facts_with_his_own_guarded_tool():
    r = get_agent_module("SAM-AG-081").verify_facts(
        facts=[{"fact": "About 1 in 10 adults lives with diabetes.", "source_id": "SRC-AAA111",
                "quote": "About 1 in 10 adults worldwide lives with diabetes."},
               {"fact": "Cinnamon cures diabetes.", "source_id": "none", "quote": "unavailable"}],
        library=_lib())
    assert (r["verified"], r["unverified"]) == (1, 1) and r["status"] == "checked"


def test_smriti_loads_only_an_approved_profile():
    sm = get_agent_module("SAM-AG-049")
    rules = {"forbidden_claims": ["miracle"], "required_disclaimers": ["Ask your doctor."]}
    assert sm.load_client_context("C1", None, rules)["status"] == "missing"
    draft = {"name": "C1 Hospital", "status": "draft", "version": 2}
    assert sm.load_client_context("C1", draft, rules)["status"] == "not_approved"
    ok = sm.load_client_context("C1", {**draft, "status": "approved", "brand_voice": "Warm", "services": ["Eye care"],
                                       "approved_by": "satya_human"}, rules)
    assert ok["status"] == "loaded" and ok["brand_voice"] == "Warm" and ok["forbidden_claims"] == ["miracle"]
    assert set(ok["unavailable"]) == {"audience", "locations", "key_messages"}


# ---------------------------------------------------------------- fetching (a person adds a page)
def test_only_https_on_allowed_public_sites(monkeypatch):
    public_dns(monkeypatch)
    assert kn.allowed_url("https://www.who.int/news-room/fact-sheets/detail/diabetes") == "www.who.int"
    for bad, why in [("http://www.who.int/x", "https"), ("https://example.com/x", "not on the list"),
                     ("https://who.int.evil.com/x", "not on the list"), ("file:///etc/passwd", "https")]:
        with pytest.raises(kn.FetchError) as e:
            kn.allowed_url(bad)
        assert why in str(e.value)
    public_dns(monkeypatch, "127.0.0.1")
    with pytest.raises(kn.FetchError) as e:
        kn.allowed_url("https://www.who.int/x")
    assert "private or local" in str(e.value)
    public_dns(monkeypatch, "10.0.0.5")
    with pytest.raises(kn.FetchError):
        kn.allowed_url("https://www.cdc.gov/x")


def test_fetch_page_follows_safe_redirects_only(monkeypatch):
    public_dns(monkeypatch)

    def handler(req):
        if req.url.path == "/old":
            return httpx.Response(301, headers={"location": "https://www.who.int/new"})
        if req.url.path == "/leave":
            return httpx.Response(302, headers={"location": "https://evil.example.com/steal"})
        if req.url.path == "/pdf":
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, content=PAGE.encode())

    t = httpx.MockTransport(handler)
    page = kn.fetch_page("https://www.who.int/old", transport=t)
    assert page["final_url"] == "https://www.who.int/new" and "1 in 10 adults" in page["text"]
    assert page["title"] == "Diabetes fact sheet" and len(page["content_hash"]) == 16
    with pytest.raises(kn.FetchError) as e:
        kn.fetch_page("https://www.who.int/leave", transport=t)
    assert "not on the list" in str(e.value)
    with pytest.raises(kn.FetchError) as e:
        kn.fetch_page("https://www.who.int/pdf", transport=t)
    assert "Only web pages" in str(e.value)


# ---------------------------------------------------------------- API: four-eyes rule and roles
async def test_profile_needs_a_second_person_and_any_edit_resets_approval():
    cid = f"CL-{uuid.uuid4().hex[:6]}"
    body = K.ProfileIn(name="Lotus Hospital", brand_voice="Warm, plain words", services=["Diabetes clinic", " "])
    p = await K.client_put(cid, body, user=CX)
    assert p["status"] == "draft" and p["version"] == 1 and p["services"] == ["Diabetes clinic"]
    with pytest.raises(HTTPException) as e:
        await K.client_approve(cid, user={**CX})
    assert e.value.status_code == 409                                    # the editor cannot approve
    p = await K.client_approve(cid, user=FOUNDER)
    assert p["status"] == "approved" and p["approved_by"] == "vikram"
    p = await K.client_put(cid, body, user=FOUNDER)                      # any edit: draft again
    assert p["status"] == "draft" and p["version"] == 2 and p["approved_by"] is None


async def test_sources_are_proposed_until_a_different_permitted_person_approves():
    text = "Regular blood sugar checks help find diabetes early. " * 6 + uuid.uuid4().hex
    src = await K.source_add(K.SourceIn(title="Screening note", publisher="Test", url="https://www.who.int/s",
                                        topics=["diabetes"], text=text), user=CX)
    assert src["status"] == "proposed" and src["added_by"] == "divya"
    with pytest.raises(HTTPException) as e:
        await K.source_approve(src["id"], user=CX)                       # role may add, not approve
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        await K.source_add(K.SourceIn(title="Same text", text=text), user=FOUNDER)
    assert e.value.status_code == 409                                    # duplicates are refused
    ok = await K.source_approve(src["id"], user=ASSURANCE)
    assert ok["status"] == "approved" and ok["approved_by"] == "satya_human"
    own = await K.source_add(K.SourceIn(title="Own", text="Walking every day helps. " * 12 + uuid.uuid4().hex),
                             user=FOUNDER)
    with pytest.raises(HTTPException) as e:
        await K.source_approve(own["id"], user=FOUNDER)                  # adder cannot approve
    assert e.value.status_code == 409
    retired = await K.source_retire(src["id"], user=FOUNDER)
    assert retired["status"] == "retired"


async def test_writes_need_a_signed_in_person():
    app = FastAPI()
    app.include_router(K.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.put("/api/knowledge/clients/X1", json={"name": "X"})
        assert r.status_code == 401
        r = await c.post("/api/knowledge/sources/fetch", json={"url": "https://www.who.int/x"})
        assert r.status_code == 401
        token = create_access_token({"sub": "vikram"})
        r = await c.post("/api/knowledge/sources/fetch", json={"url": "http://www.who.int/x"},
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400 and "https" in r.json()["detail"]
        assert (await c.get("/api/knowledge/clients")).status_code == 200


def test_extract_prefers_main_content_and_the_page_title():
    html = ("<html><head><title>Type 2 Diabetes | MedlinePlus</title></head><body>"
            "<div class='banner'>Official websites use .gov. A .gov website belongs to an official government organization.</div>"
            "<svg><title>Lock</title></svg><main><h1>Type 2 Diabetes</h1><p>" + "Type 2 diabetes is the most common type. " * 8 +
            "</p></main><div>Related links and other site furniture</div></body></html>")
    title, text = kn.extract_text(html)
    assert title == "Type 2 Diabetes | MedlinePlus"
    assert text.startswith("Type 2 Diabetes") and "Official websites" not in text and "furniture" not in text
