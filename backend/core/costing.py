"""Cost and KPI arithmetic, in code (config/costing.yaml). No model is involved.

cost(metrics, rates)      money from measured usage; unknown rates stay "unavailable"
evaluate(metrics, kpis)   each KPI's measured value against its target
"""
from __future__ import annotations

import os
from functools import lru_cache

import yaml

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                           "config", "costing.yaml")


@lru_cache
def config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _num(v):
    return None if v is None else float(v)


def cost(metrics: dict, rates: dict | None = None, currency: str | None = None) -> dict:
    rates = rates if rates is not None else (config().get("rates") or {})
    currency = currency or config().get("currency") or ""
    parts, unknown = {}, []

    r = _num(rates.get("model_cost_per_1k_tokens"))
    if r is None:
        unknown.append("model tokens (no rate)")
    else:
        parts["model_tokens"] = round(int(metrics.get("tokens") or 0) / 1000.0 * r, 4)

    r = _num(rates.get("compute_cost_per_model_hour"))
    if r is None:
        unknown.append("machine time (no rate)")
    else:
        parts["compute"] = round(float(metrics.get("model_seconds") or 0) / 3600.0 * r, 4)

    hr, mins = _num(rates.get("human_rate_per_hour")), _num(rates.get("review_minutes_per_decision"))
    if hr is None or mins is None:
        unknown.append("human review time (no rate)")
    else:
        parts["human_review"] = round(int(metrics.get("human_decisions") or 0) * mins / 60.0 * hr, 2)

    known = round(sum(parts.values()), 4)
    accepted = int(metrics.get("accepted_deliverables") or 0)
    complete = not unknown
    out = {
        "currency": currency,
        "parts": parts,
        "unavailable_parts": unknown,
        "total_cost": known if complete else "unavailable",
        "known_cost": known,
        "accepted_deliverables": accepted,
        "cost_per_accepted_deliverable": (round(known / accepted, 4) if complete and accepted else "unavailable"),
        # measured resources per accepted deliverable (always real, even without money rates)
        "tokens_per_accepted_deliverable": (round(int(metrics.get("tokens") or 0) / accepted) if accepted else "unavailable"),
        "model_minutes_per_accepted_deliverable": (round(float(metrics.get("model_seconds") or 0) / 60.0 / accepted, 2)
                                                   if accepted else "unavailable"),
        "status": "computed" if complete and accepted else "partial",
    }
    if not accepted:
        out["note"] = "No deliverable has been accepted at Gate 2, so there is no cost per accepted deliverable."
    elif unknown:
        out["note"] = "Some rates are not set in config/costing.yaml: " + ", ".join(unknown) + "."
    return out


def evaluate(metrics: dict, kpis: dict | None = None) -> dict:
    kpis = kpis if kpis is not None else (config().get("kpis") or {})
    rows = []
    for name, spec in kpis.items():
        value = metrics.get(name)
        target = spec.get("target")
        better = spec.get("better", "higher")
        if value is None or target is None:
            met = None
        elif better == "lower":
            met = float(value) <= float(target)
        else:
            met = float(value) >= float(target)
        rows.append({"kpi": name, "value": value, "target": target, "better": better, "met": met})
    missed = [r["kpi"] for r in rows if r["met"] is False]
    unknown = [r["kpi"] for r in rows if r["met"] is None]
    return {
        "kpis": rows,
        "missed": missed,
        "not_measured": unknown,
        "status": "on_target" if not missed and not unknown else ("off_target" if missed else "partly_measured"),
    }
