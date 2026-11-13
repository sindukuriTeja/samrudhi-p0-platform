"""Tenant isolation, checked in code (architecture §11.2: an agent sees only its client's data).

Before any agent step runs, the runner checks the data it is about to hand over (the hand-over
records, tool arguments, sources, work packages) for another client's identifiers or names. If
any is found, the step is not run and the project stops for a person. The human team's own
instructions are not scanned (people may mention other clients); the agents' output is checked
again by Gopniya.
"""
from __future__ import annotations

import json
import re

MIN_NAME = 5


def markers(own_client: str, clients: list[tuple[str, list[str]]]) -> list[tuple[str, re.Pattern]]:
    """(label, pattern) for every OTHER client: its id (exact case) and its names (any case)."""
    own_names = {n.lower() for cid, names in clients if cid == own_client for n in names if n}
    out = []
    for cid, names in clients:
        if not cid or cid == own_client:
            continue
        if "-" in cid:   # real client ids look like DEMO-HEALTHCARE-01; short words are not ids
            out.append((cid, re.compile(r"(?<![\w-])" + re.escape(cid) + r"(?![\w-])")))
        for n in names:
            if n and len(n) >= MIN_NAME and n.lower() not in own_names:
                out.append((n, re.compile(r"\b" + re.escape(n) + r"\b", re.I)))
    return out


# Not data: the human team's instructions, and the screening rules that list other clients'
# names precisely so that Gopniya can block them.
SKIP_KEYS = ("human_instructions", "other_client_names")


def _strip(v, skip):
    if isinstance(v, dict):
        return {k: _strip(x, skip) for k, x in v.items() if k not in skip}
    if isinstance(v, list):
        return [_strip(x, skip) for x in v]
    return v


def find_foreign(data, marks: list[tuple[str, re.Pattern]], skip_keys=SKIP_KEYS) -> list[str]:
    """Labels of other clients whose id or name appears in the data."""
    if not marks:
        return []
    text = json.dumps(_strip(data, set(skip_keys)), ensure_ascii=False, default=str)
    found = []
    for label, pat in marks:
        if label not in found and pat.search(text):
            found.append(label)
    return found
