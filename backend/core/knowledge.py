"""Real information for the agents: source fetching, passage retrieval and fact verification.

Pure code, no model. Settings in config/knowledge.yaml.

- fetch_page(url):     a person adds a page from an allowed https site; private and local
                       addresses are refused (no server-side request to internal hosts).
- extract_text(html):  readable text from a page (scripts, styles and navigation dropped).
- retrieve(...):       the approved passages that match the project, for Anvesh.
- verify_fact(...):    a fact is verified only if its quote is in the cited approved source
                       and the fact's figures appear in that quote.
"""
from __future__ import annotations

import hashlib
import ipaddress
import os
import re
import socket
from functools import lru_cache
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx
import yaml

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                           "config", "knowledge.yaml")

STOP = set("""a an and are as at be been but by can could do does for from had has have how i if in into is it its
may more most not of on or our over so such than that the their them then there these they this to too up us
was we were what when which who why will with without you your about after also any all each other only very
just per new one two use used using get make made many much some""".split())


@lru_cache
def config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class FetchError(Exception):
    """The page cannot be added (the message says why, for the person adding it)."""


# ---------------------------------------------------------------------------
# text helpers
# ---------------------------------------------------------------------------

def norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w%.]+", " ", (text or "").lower()).replace(". ", " ").split()).rstrip(".")


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9%]+(?:\.[0-9]+)?", (text or "").lower())


def key_words(text: str) -> set[str]:
    return {w for w in words(text) if (len(w) > 2 or w.isdigit()) and w not in STOP}


def figures(text: str) -> set[str]:
    """Numbers in a text ("830", "1.5", "40%"), with thousands separators removed."""
    out = set()
    for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", text or ""):
        out.add(m.group(0).replace(",", "").rstrip("."))
    return out


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [p.strip() for p in parts if len(p.strip()) > 3]


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# fetching a page (only when a signed-in person asks)
# ---------------------------------------------------------------------------

class _TextParser(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "header", "footer", "form", "button", "iframe", "aside"}
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr", "section", "article", "td", "dd", "dt"}

    MAIN = {"main", "article"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.main, self.skip, self.in_main = [], [], 0, 0
        self.title, self._in_title = "", False

    def _emit(self, text):
        self.out.append(text)
        if self.in_main:
            self.main.append(text)

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag in self.MAIN or dict(attrs).get("role") == "main":
            self.in_main += 1
        if tag == "title" and not self.skip and not self.title:
            self._in_title = True        # the page's own title, not an icon's <svg><title>
        if tag in self.BLOCK:
            self._emit("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag in self.MAIN and self.in_main:
            self.in_main -= 1
        if tag == "title":
            self._in_title = False
        if tag in self.BLOCK:
            self._emit("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip:
            self._emit(data)


def _clean(parts: list[str]) -> str:
    lines = [" ".join(x.split()) for x in "".join(parts).split("\n")]
    return "\n".join(x for x in lines if len(x) > 1)


def extract_text(html: str) -> tuple[str, str]:
    """(title, text) of an HTML page; the page's <main>/<article> content when it has one."""
    p = _TextParser()
    p.feed(html or "")
    main = _clean(p.main)
    text = main if len(main) >= 200 else _clean(p.out)
    return " ".join(p.title.split()), text


def allowed_url(url: str) -> str:
    """Return the host if the URL may be fetched, else raise FetchError."""
    u = urlparse((url or "").strip())
    if u.scheme != "https":
        raise FetchError("Only https:// pages can be added.")
    host = (u.hostname or "").lower().rstrip(".")
    if not host:
        raise FetchError("The address has no host.")
    domains = [d.lower() for d in (config().get("fetch") or {}).get("allowed_domains") or []]
    if not any(host == d or host.endswith("." + d) for d in domains):
        raise FetchError(f"{host} is not on the list of allowed sites (config/knowledge.yaml).")
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise FetchError(f"{host} could not be found.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast \
                or ip.is_unspecified:
            raise FetchError(f"{host} resolves to a private or local address; it cannot be fetched.")
    return host


def fetch_page(url: str, transport: httpx.BaseTransport | None = None) -> dict:
    """Fetch an allowed page: {url, final_url, title, text, content_hash}. Raises FetchError."""
    cfg = config().get("fetch") or {}
    max_bytes = int(cfg.get("max_bytes", 2_000_000))
    current = url.strip()
    with httpx.Client(timeout=float(cfg.get("timeout_s", 20)), follow_redirects=False, transport=transport,
                      headers={"User-Agent": "SamrudhiSourceLibrary/1.0"}) as client:
        for _ in range(int(cfg.get("max_redirects", 3)) + 1):
            allowed_url(current)                      # checked again after every redirect
            with client.stream("GET", current) as r:
                if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                    current = urljoin(current, r.headers["location"])
                    continue
                if r.status_code != 200:
                    raise FetchError(f"The site answered {r.status_code}.")
                ctype = r.headers.get("content-type", "").lower()
                if "html" not in ctype and "text/plain" not in ctype:
                    raise FetchError(f"Only web pages can be added (this is {ctype or 'unknown'}).")
                body = b""
                for chunk in r.iter_bytes():
                    body += chunk
                    if len(body) > max_bytes:
                        raise FetchError("The page is too large.")
                raw = body.decode(r.encoding or "utf-8", errors="replace")
                break
        else:
            raise FetchError("Too many redirects.")
    title, text = extract_text(raw) if "html" in ctype else ("", raw)
    text = text[: int(cfg.get("max_text_chars", 30000))]
    if len(text) < 200:
        raise FetchError("The page has almost no readable text.")
    return {"url": url.strip(), "final_url": current, "title": title, "text": text, "content_hash": content_hash(text)}


# ---------------------------------------------------------------------------
# retrieval: which approved passages Anvesh gets
# ---------------------------------------------------------------------------

def passages(text: str, size: int | None = None) -> list[str]:
    size = size or int((config().get("retrieval") or {}).get("passage_chars", 450))
    out, cur = [], ""
    for sent in sentences(text):
        if cur and len(cur) + len(sent) + 1 > size:
            out.append(cur)
            cur = ""
        cur = f"{cur} {sent}".strip()
    if cur:
        out.append(cur)
    return out


def retrieve(query: str, sources: list[dict]) -> list[dict]:
    """Pick the approved passages that best match the query.

    sources: [{id, title, publisher, url, topics, text}] (approved only).
    Returns [{source_id, title, publisher, url, passages: [{passage_id, text}]}].
    """
    cfg = config().get("retrieval") or {}
    q = key_words(query)
    if not q:
        return []
    scored = []
    for src in sources:
        head = key_words(" ".join([src.get("title") or "", " ".join(src.get("topics") or [])]))
        body = key_words(src.get("text") or "")
        score = 3 * len(q & head) + len(q & body)
        if score:
            scored.append((score, src))
    scored.sort(key=lambda x: -x[0])
    out, budget = [], int(cfg.get("max_total_chars", 2000))
    for _, src in scored[: int(cfg.get("max_sources", 4))]:
        ps = passages(src.get("text") or "")
        ranked = sorted(enumerate(ps, start=1), key=lambda ip: -len(q & key_words(ip[1])))
        chosen = []
        for i, ptext in ranked[: int(cfg.get("passages_per_source", 2))]:
            if not (q & key_words(ptext)) or budget <= 0:
                continue
            ptext = ptext[:budget]
            budget -= len(ptext)
            chosen.append({"passage_id": f"{src['id']}#{i}", "text": ptext})
        if chosen:
            out.append({"source_id": src["id"], "title": src.get("title"), "publisher": src.get("publisher"),
                        "url": src.get("url"), "passages": chosen})
    return out


# ---------------------------------------------------------------------------
# verification: is the fact really in the approved source?
# ---------------------------------------------------------------------------

def quote_in_source(quote: str, source_text: str) -> bool:
    vcfg = config().get("verification") or {}
    qw = words(quote)
    if len(qw) < int(vcfg.get("min_quote_words", 5)):
        return False
    nq = " ".join(qw)
    if nq in " ".join(words(source_text)):
        return True
    need = float(vcfg.get("min_quote_overlap", 0.8))
    qset = set(qw)
    for sent in sentences(source_text):
        if len(qset & set(words(sent))) / len(qset) >= need:
            return True
    return False


def verify_fact(item: dict, library: dict[str, dict]) -> dict:
    """Check one fact {fact, source_id, quote} against approved sources {id: source}.

    Returns the fact with verified, reason and the source's real title/publisher/url (taken
    from the library, never from the model).
    """
    vcfg = config().get("verification") or {}
    fact = str(item.get("fact") or "").strip()
    quote = str(item.get("quote") or "").strip()
    sid = str(item.get("source_id") or "").strip().split("#")[0].upper()
    src = library.get(sid)
    out = {"fact": fact, "quote": quote, "source_id": sid if src else (item.get("source_id") or ""),
           "verified": False, "source_title": None, "publisher": None, "url": None}
    if src is None:
        out["reason"] = "not from an approved source in the library"
        return out
    out.update(source_title=src.get("title"), publisher=src.get("publisher"), url=src.get("url"))
    if not quote_in_source(quote, src.get("text") or ""):
        out["reason"] = "the quote was not found in the source"
        return out
    missing = figures(fact) - figures(quote)
    if missing:
        out["reason"] = "figures not in the quote: " + ", ".join(sorted(missing))
        return out
    fk = key_words(fact)
    if fk and len(fk & key_words(quote)) / len(fk) < float(vcfg.get("min_fact_overlap", 0.3)):
        out["reason"] = "the fact says something the quote does not"
        return out
    out["verified"], out["reason"] = True, "quote found in the approved source"
    return out
