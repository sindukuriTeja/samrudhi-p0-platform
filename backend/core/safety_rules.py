"""Content safety rules, enforced in code (config/safety_rules.yaml).

The rules are plain data; this module does all the matching so the checking agents
(Shuddhi, Gunvatta, Swasthya, Gopniya) and the release guard (Prakash) apply exactly the
same rules. Nothing here calls a model: every decision is reproducible.

Each finding is {"post": <1-based number or None>, "rule": <rule kind>, "detail": <text>}.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache

import yaml

RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                          "config", "safety_rules.yaml")

PLACEHOLDERS = {"", "unavailable", "n/a", "na", "none", "tbd", "<text>"}
STAT_RE = re.compile(r"(\d+(?:\.\d+)?\s*%|\b\d+\s+(?:in|out\s+of)\s+\d+\b)", re.I)

# rule kinds
FORBIDDEN_CLAIM = "forbidden_claim"
FORBIDDEN_PATTERN = "forbidden_pattern"
MISSING_DISCLAIMER = "missing_disclaimer"
MISSING_FIELD = "missing_field"
TOO_LONG = "too_long"
UNSUPPORTED_STATISTIC = "unsupported_statistic"
OTHER_CLIENT = "other_client"


@lru_cache
def _load() -> dict:
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def reload() -> None:
    _load.cache_clear()


def _norm(text: str) -> str:
    """Lower case, punctuation removed, whitespace collapsed (for disclaimer and phrase matching)."""
    return " ".join(re.sub(r"[^\w%]+", " ", (text or "").lower()).split())


def rules_for(client_id: str | None) -> dict:
    """Global rules plus the client's own (a client can add rules, never remove them)."""
    data = _load()
    g = data.get("global") or {}
    clients = data.get("clients") or {}
    c = clients.get(client_id or "") or {}

    def merged(key):
        out = []
        for x in list(g.get(key) or []) + list(c.get(key) or []):
            if x not in out:
                out.append(x)
        return out

    others = []
    for cid, info in clients.items():
        if cid == client_id:
            continue
        for name in [(info or {}).get("name")] + list((info or {}).get("aliases") or []):
            if name and name not in others:
                others.append(name)
    return {
        "client_id": client_id,
        "client_name": c.get("name"),
        "known_client": bool(c),
        "forbidden_claims": merged("forbidden_claims"),
        "forbidden_patterns": merged("forbidden_patterns"),
        "required_disclaimers": merged("required_disclaimers"),
        "post_fields": list(c.get("post_fields") or g.get("post_fields") or []),
        "max_caption_chars": int(c.get("max_caption_chars") or g.get("max_caption_chars") or 0) or None,
        "statistics_need_evidence": bool(c.get("statistics_need_evidence", g.get("statistics_need_evidence", True))),
        "other_client_names": others,
    }


def post_text(post) -> str:
    if isinstance(post, dict):
        return "\n".join(str(v) for k, v in post.items() if not str(k).startswith("_") and isinstance(v, (str, int, float)))
    return str(post or "")


def _as_posts(posts=None, content: str | None = None) -> list:
    if isinstance(posts, list) and posts:
        return posts
    return [content] if content else []


def find_claims(text: str, forbidden_claims=(), forbidden_patterns=()) -> list[tuple[str, str]]:
    """[(rule kind, detail)] for every forbidden phrase or pattern in the text."""
    low = (text or "").lower()
    norm = _norm(text)
    out = []
    for phrase in forbidden_claims or []:
        p = str(phrase).lower().strip()
        if p and (p in low or _norm(p) in norm):
            out.append((FORBIDDEN_CLAIM, f'forbidden claim "{phrase}"'))
    for item in forbidden_patterns or []:
        pattern = item.get("pattern") if isinstance(item, dict) else str(item)
        reason = item.get("reason") if isinstance(item, dict) else "forbidden wording"
        try:
            m = re.search(pattern, text or "", re.I)
        except re.error:
            continue
        if m:
            out.append((FORBIDDEN_PATTERN, f'{reason}: "{m.group(0)}"'))
    return out


def has_disclaimer(text: str, disclaimers) -> bool:
    if not disclaimers:
        return True
    norm = _norm(text)
    return any(_norm(d) in norm for d in disclaimers)


def unsupported_statistics(text: str, evidence: str | None) -> list[str]:
    """Figures such as "40%" or "1 in 10" that do not appear in the evidence text."""
    ev = _norm(evidence or "").replace(" %", "%")
    out = []
    for m in STAT_RE.finditer(text or ""):
        fig = _norm(m.group(0)).replace(" %", "%")
        if fig and fig not in ev and fig not in out:
            out.append(fig)
    return out


def screen(posts=None, rules: dict | None = None, *, content: str | None = None, evidence: str | None = None,
           only: set[str] | None = None) -> dict:
    """Check posts (or one block of text) against the rules.

    only: limit to some rule kinds, e.g. {"forbidden_claim", "forbidden_pattern"}.
    """
    rules = rules or rules_for(None)
    want = (lambda k: only is None or k in only)
    items = _as_posts(posts, content)
    findings = []
    seen_text = set()
    for i, post in enumerate(items, start=1):
        n = i if isinstance(posts, list) and posts else None
        text = post_text(post)
        if want(FORBIDDEN_CLAIM) or want(FORBIDDEN_PATTERN):
            for kind, detail in find_claims(text, rules.get("forbidden_claims"), rules.get("forbidden_patterns")):
                if want(kind):
                    findings.append({"post": n, "rule": kind, "detail": detail})
        if want(MISSING_DISCLAIMER) and not has_disclaimer(text, rules.get("required_disclaimers")):
            findings.append({"post": n, "rule": MISSING_DISCLAIMER,
                             "detail": "required disclaimer missing: \"" + rules["required_disclaimers"][0] + "\""})
        if isinstance(post, dict):
            if want(MISSING_FIELD):
                for f in rules.get("post_fields") or []:
                    if str(post.get(f, "")).strip().lower() in PLACEHOLDERS:
                        findings.append({"post": n, "rule": MISSING_FIELD, "detail": f"{f} is empty"})
            cap = str(post.get("caption") or "")
            limit = rules.get("max_caption_chars")
            if want(TOO_LONG) and limit and len(cap) > limit:
                findings.append({"post": n, "rule": TOO_LONG,
                                 "detail": f"caption has {len(cap)} characters (limit {limit})"})
            key = _norm(cap)
            if want(MISSING_FIELD) and key and key in seen_text:
                findings.append({"post": n, "rule": MISSING_FIELD, "detail": "caption repeats an earlier post"})
            seen_text.add(key)
        if want(UNSUPPORTED_STATISTIC) and rules.get("statistics_need_evidence") and evidence is not None:
            for fig in unsupported_statistics(text, evidence):
                findings.append({"post": n, "rule": UNSUPPORTED_STATISTIC,
                                 "detail": f'figure "{fig}" is not in the research pack'})
        if want(OTHER_CLIENT):
            low = text.lower()
            for name in rules.get("other_client_names") or []:
                if name.lower() in low:
                    findings.append({"post": n, "rule": OTHER_CLIENT, "detail": f'names another client "{name}"'})
    return {"findings": findings, "passed": not findings, "posts_checked": len(items)}


def describe(f: dict) -> str:
    return (f"post {f['post']}: " if f.get("post") else "") + f["detail"]


def prompt_text(rules: dict) -> str:
    """The rules in a few lines, for the writer and the screener (the code still enforces them)."""
    lines = []
    if rules.get("required_disclaimers"):
        lines.append("End every caption with this disclaimer, word for word: \"" + rules["required_disclaimers"][0] + "\"")
    if rules.get("forbidden_claims"):
        lines.append("Never write: " + "; ".join(rules["forbidden_claims"][:20]) + ".")
    reasons = [p.get("reason") for p in rules.get("forbidden_patterns") or [] if isinstance(p, dict) and p.get("reason")]
    if reasons:
        lines.append("Also not allowed: " + "; ".join(reasons) + ".")
    if rules.get("statistics_need_evidence"):
        lines.append("Use a number or percentage only if it is in the research pack.")
    if rules.get("other_client_names"):
        lines.append("Never mention other clients.")
    return " ".join(lines)


# ---------------------------------------------------------------------------
# what the code has already decided (so a model reviewer neither repeats nor contradicts it)
# ---------------------------------------------------------------------------

# Rules the code checks exactly; a model's complaint about one of them is tested against the code.
VERIFIABLE = {
    MISSING_DISCLAIMER: re.compile(r"disclaimer", re.I),
    OTHER_CLIENT: re.compile(r"\b(other|another) client|competitor", re.I),
    MISSING_FIELD: re.compile(r"\b(missing|no|lacks?|without)\s+(a\s+|the\s+)?(headline|caption|call[ -]to[ -]action)"
                              r"|\b(headline|caption|call[ -]to[ -]action)s?\s+(is|are)\s+(missing|empty)", re.I),
}


def code_summary(findings: list[dict], posts_checked: int, rules: dict) -> str:
    """One paragraph telling a reviewer what the code has verified on the current posts."""
    if not posts_checked:
        return ""
    kinds = {f["rule"] for f in findings}
    lines = []
    if rules.get("required_disclaimers"):
        lines.append("the required disclaimer is " + ("MISSING in some posts" if MISSING_DISCLAIMER in kinds
                                                        else f"present in all {posts_checked} posts"))
    lines.append("forbidden claims and wording: " + ("FOUND" if kinds & {FORBIDDEN_CLAIM, FORBIDDEN_PATTERN} else "none"))
    lines.append("headline, caption and call to action: " + ("some are EMPTY" if MISSING_FIELD in kinds else "filled in"))
    lines.append("other clients named: " + ("YES" if OTHER_CLIENT in kinds else "none"))
    if UNSUPPORTED_STATISTIC in kinds:
        lines.append("some figures are NOT in the verified research")
    text = "The code has already checked these posts: " + "; ".join(lines) + "."
    if findings:
        text += " Code findings: " + "; ".join(describe(f) for f in findings[:8]) + "."
    return text + " Do not re-check these; review medical accuracy, facts against the research, and brand fit."


# A sentence that only points back ("This is a critical issue…") belongs to the sentence before it.
_FOLLOW_ON = re.compile(r"^(this|these|that|those|it|they|such|which|please|so|therefore|hence)\b", re.I)


def split_reasons(reasons) -> list[str]:
    items = reasons if isinstance(reasons, list) else [reasons]
    out = []
    for r in items:
        first = True
        for part in re.split(r"(?<=[.!?;])\s+", str(r or "")):
            part = part.strip()
            if not part:
                continue
            if out and not first and _FOLLOW_ON.match(part):
                out[-1] = f"{out[-1]} {part}"
            else:
                out.append(part)
            first = False
    return out


def overrule(reasons, findings: list[dict], posts_checked: int) -> tuple[list[str], list[str]]:
    """(kept, overruled): a reason about a rule the code verified as satisfied is overruled."""
    if not posts_checked:
        return split_reasons(reasons), []
    kinds = {f["rule"] for f in findings}
    kept, dropped = [], []
    for r in split_reasons(reasons):
        hit = [k for k, pat in VERIFIABLE.items() if pat.search(r)]
        if hit and all(k not in kinds for k in hit):
            dropped.append(r)
        else:
            kept.append(r)
    return kept, dropped
