"""Structured outputs for project steps: describe, request, parse and validate them in code.

A step's `output` in config/project_flows.yaml is a small schema:
    str | bool | int          a scalar field
    [<schema>]                a list of items
    {field: <schema>, ...}    an object
Example:
    output:
      goal: str
      owners: [{area: str, agent: str}]

The model is asked for exactly this shape (Ollama JSON mode); the reply is validated here.
Values the agent does not know must be the string "unavailable" — never invented.
"""
import json
import re

SCALARS = {"str", "bool", "int"}


def example(spec):
    """A JSON template the model fills in."""
    if isinstance(spec, dict):
        return {k: example(v) for k, v in spec.items()}
    if isinstance(spec, list):
        return [example(spec[0])] if spec else []
    return {"str": "<text>", "bool": True, "int": 0}.get(spec, "<text>")


def validate(data, spec, path: str = "") -> list[str]:
    """Return a list of problems (empty when the data matches the schema)."""
    where = path or "the answer"
    if isinstance(spec, dict):
        if not isinstance(data, dict):
            return [f"{where} must be an object"]
        errors = []
        for key, sub in spec.items():
            if key not in data:
                errors.append(f"{path + '.' if path else ''}{key} is missing")
            else:
                errors += validate(data[key], sub, f"{path + '.' if path else ''}{key}")
        return errors
    if isinstance(spec, list):
        if not isinstance(data, list):
            return [f"{where} must be a list"]
        errors = []
        for i, item in enumerate(data[:50]):
            errors += validate(item, spec[0], f"{path}[{i}]") if spec else []
        return errors
    if spec == "bool":
        return [] if isinstance(data, bool) else [f"{where} must be true or false"]
    if spec == "int":
        return [] if isinstance(data, int) and not isinstance(data, bool) else [f"{where} must be a whole number"]
    # "str": accept numbers too (dates, counts), but not objects, lists or empty text
    if isinstance(data, (dict, list)) or data is None:
        return [f"{where} must be text"]
    return [] if str(data).strip() else [f"{where} is empty (write \"unavailable\" if unknown)"]


def coerce(data, spec):
    """Normalise scalars to the schema's types after validation (numbers in text fields become text)."""
    if isinstance(spec, dict) and isinstance(data, dict):
        return {k: (coerce(v, spec[k]) if k in spec else v) for k, v in data.items()}
    if isinstance(spec, list) and isinstance(data, list):
        return [coerce(x, spec[0]) for x in data] if spec else data
    if spec == "str" and data is not None and not isinstance(data, (dict, list)):
        return str(data)
    return data


def apply_overrides(data: dict, overrides: dict | None) -> dict:
    """Force values the model must not decide, e.g. {"facts[].verified": false}.

    Path syntax: "field" or "list[].field" (applies to every item of the list).
    """
    for path, value in (overrides or {}).items():
        if "[]." in path:
            field, _, sub = path.partition("[].")
            for item in data.get(field) or []:
                if isinstance(item, dict):
                    item[sub] = value
        else:
            data[path] = value
    return data


def extract_json(text: str):
    """Find the JSON object in a model reply (JSON mode returns it bare; tolerate fences and prose)."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I)
    try:
        val = json.loads(t)
        return val if isinstance(val, dict) else None
    except Exception:
        pass
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        try:
            val = json.loads(t[start:end + 1])
            return val if isinstance(val, dict) else None
        except Exception:
            return None
    return None


def flatten_text(data) -> str:
    """All text in a structured record, for code checks such as claim screening."""
    out = []

    def walk(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if not str(k).startswith("_"):
                    walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, str):
            out.append(v)
    walk(data)
    return "\n".join(out)


def public(data: dict | None) -> dict:
    """A step's structured record without the runner's private keys."""
    return {k: v for k, v in (data or {}).items() if not str(k).startswith("_")}


def trim(data, max_chars: int = 2500):
    """Keep a handed-over record within a size the local model can read in time."""
    text = json.dumps(data, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return data
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if isinstance(v, list) and len(v) > 6:
                v = v[:6] + [f"… {len(v) - 6} more"]
            if isinstance(v, str) and len(v) > 400:
                v = v[:400] + "…"
            out[k] = v
        return out
    return text[:max_chars] + "…"
