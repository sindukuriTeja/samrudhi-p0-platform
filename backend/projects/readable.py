"""Turn agent output into plain readable text for the conversation.

Agents return free text from the model. The Control Room must never show code
or raw JSON, so this module:
  - turns JSON (whole output or fenced JSON blocks) into "Label: value" lines
  - drops fenced code blocks in programming languages
  - removes Markdown symbols (headings, bold, inline code, tables)
It never adds information that the agent did not write.
"""
import json
import re

_CODE_LANGS = {
    "python", "py", "js", "javascript", "ts", "typescript", "bash", "sh", "shell",
    "sql", "html", "css", "java", "c", "cpp", "go", "rust", "php", "ruby", "xml",
    "powershell", "ps1", "jsx", "tsx", "yaml", "yml",
}
_FENCE = re.compile(r"```([A-Za-z0-9_+-]*)[^\n]*\n(.*?)```", re.S)


def _label(key: str) -> str:
    key = re.sub(r"[_\-]+", " ", str(key)).strip()
    key = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", key)
    return key[:1].upper() + key[1:].lower() if key else key


def _flatten(obj, depth: int = 0) -> list[str]:
    pad = "  " * depth
    lines: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{_label(k)}:")
                lines.extend(_flatten(v, depth + 1))
            else:
                lines.append(f"{pad}{_label(k)}: {_scalar(v)}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                sub = _flatten(item, depth + 1)
                if sub:
                    sub[0] = f"{pad}• " + sub[0].lstrip()
                lines.extend(sub)
            else:
                lines.append(f"{pad}• {_scalar(item)}")
    else:
        lines.append(f"{pad}{_scalar(obj)}")
    return lines


def _scalar(v) -> str:
    if v is None or v == "":
        return "unavailable"
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v)


def _try_json(text: str):
    t = text.strip()
    if not t or t[0] not in "[{":
        return None
    try:
        return json.loads(t)
    except Exception:
        return None


def _strip_markdown(text: str) -> str:
    out = []
    for line in text.splitlines():
        s = line.rstrip()
        if re.fullmatch(r"\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*", s):
            continue  # table separator row
        if s.strip().startswith("|") and s.strip().endswith("|"):
            cells = [c.strip() for c in s.strip().strip("|").split("|")]
            s = " · ".join(c for c in cells if c)
        s = re.sub(r"^\s{0,3}#{1,6}\s*", "", s)          # headings
        s = re.sub(r"^(\s*)[-*+]\s+", r"\1• ", s)          # bullets
        s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)             # bold
        s = re.sub(r"__(.+?)__", r"\1", s)
        s = re.sub(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", s)  # italics
        s = re.sub(r"`([^`]+)`", r"\1", s)                 # inline code
        s = re.sub(r"^\s*>\s?", "", s)                     # quotes
        out.append(s)
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def readable(text: str | None) -> str:
    if not text:
        return ""
    whole = _try_json(text)
    if whole is not None:
        return "\n".join(_flatten(whole)).strip()

    removed_code = False

    def _fence(m: re.Match) -> str:
        nonlocal removed_code
        lang, body = m.group(1).lower(), m.group(2)
        data = _try_json(body)
        if data is not None:
            return "\n".join(_flatten(data)) + "\n"
        if lang in _CODE_LANGS:
            removed_code = True
            return ""
        return body

    text = _FENCE.sub(_fence, text)
    text = text.replace("```", "")
    result = _strip_markdown(text)
    if not result and removed_code:
        return "The agent returned only code, which is not shown here."
    return result


def one_line(text: str | None, limit: int = 160) -> str:
    """First meaningful line / sentence, for summaries and timelines."""
    if not text:
        return ""
    lines = [ln.strip(" •-\t") for ln in text.splitlines()]
    lines = [ln for ln in lines if len(ln) >= 3]
    if not lines:
        return ""
    # Prefer the first real sentence over a short heading such as "Client Brief Capture".
    pick = next((ln for ln in lines if len(ln.split()) >= 6 and not ln.endswith(":")), lines[0])
    m = re.match(r"(.+?[.!?])(\s|$)", pick)
    first = m.group(1) if m and len(m.group(1)) >= 20 else pick
    return first if len(first) <= limit else first[: limit - 1].rstrip() + "…"
