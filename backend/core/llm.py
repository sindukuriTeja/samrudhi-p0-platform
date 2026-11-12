"""Serialized LLM queue wrapper over Ollama.

Architecture principle: ONE 7B model, calls SERIALIZED and QUEUED.
All agents share a single in-process lock so LLM calls never run concurrently
(the model is memory-heavy; concurrency would OOM or thrash).
"""
import asyncio
import time
from dataclasses import dataclass

import httpx

from config.settings import get_settings

settings = get_settings()

# Single lock serializes ALL LLM calls across all agents
_llm_lock = asyncio.Lock()


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int
    response_tokens: int
    latency_s: float
    model: str


async def _count_tokens_approx(text: str) -> int:
    """Rough token estimate (~4 chars/token). Production: use model tokenizer."""
    return max(1, len(text) // 4)


async def generate(
    prompt: str,
    *,
    system: str | None = None,
    model: str | None = None,
    temperature: float = 0.3,
    timeout_s: float = 120.0,
    format: str | None = None,
) -> LLMResult:
    """Call Ollama with the given prompt, serialized across all agents.

    If Ollama is down, raises ConnectionError (agent must report 'model
    unavailable' honestly — never fake output).
    """
    model = model or settings.ollama_model
    url = f"{settings.ollama_url.rstrip('/')}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }
    if system:
        payload["system"] = system
    if format == "json":
        # Ollama JSON mode: the model must return one valid JSON object.
        payload["format"] = "json"

    start = time.monotonic()
    async with _llm_lock:  # serialize all LLM calls
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

    latency = time.monotonic() - start
    response_text: str = data.get("response", "")
    return LLMResult(
        text=response_text,
        prompt_tokens=data.get("prompt_eval_count", await _count_tokens_approx(prompt)),
        response_tokens=data.get("eval_count", await _count_tokens_approx(response_text)),
        latency_s=round(latency, 2),
        model=model,
    )


async def check_ollama_health() -> dict:
    """Return Ollama health status. Used by health endpoints."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_url.rstrip('/')}/api/tags")
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                return {
                    "status": "healthy",
                    "url": settings.ollama_url,
                    "model": settings.ollama_model,
                    "available_models": models,
                    "configured_model_present": settings.ollama_model in models,
                }
            return {"status": "unhealthy", "http_status": resp.status_code}
    except Exception as e:
        return {"status": "unreachable", "error": str(e)}
