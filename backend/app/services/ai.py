"""AI provider client for any OpenAI-compatible chat completions API.

Examples: NVIDIA NIM (https://integrate.api.nvidia.com/v1), OpenAI, Groq,
OpenRouter, Ollama (http://127.0.0.1:11434/v1).

Security rules enforced here:
  * The API key is read only from the local secrets store / environment.
  * The key is sent only to the configured provider endpoint, never logged.
  * Provider errors are mapped to clear, actionable messages.
"""
import json
import time
from typing import Any, AsyncIterator, Optional

import httpx

from .. import db, secrets
from ..config import settings
from ..errors import ProviderNotConfiguredError, ProviderRequestError


def get_provider_config() -> Optional[dict]:
    """Resolve the active provider: Settings-page config first, env fallback."""
    row = db.query_one("SELECT * FROM provider_config WHERE id = 1")
    if row:
        key = secrets.get_stored_key()
        if not key:
            key = settings.env_provider["key"] or None
        return {
            "name": row["provider_name"],
            "base_url": row["base_url"],
            "model": row["model"],
            "key": key,
            "source": "settings",
        }
    env = settings.env_provider
    if env["base_url"] and env["model"] and env["key"]:
        return {
            "name": env["name"] or "Environment provider",
            "base_url": env["base_url"],
            "model": env["model"],
            "key": env["key"],
            "source": "env",
        }
    return None


def require_provider_config() -> dict:
    cfg = get_provider_config()
    if cfg is None or not cfg["key"]:
        raise ProviderNotConfiguredError()
    return cfg


def validate_provider_input(base_url: str) -> None:
    if not base_url.startswith(("http://", "https://")):
        raise ValueError("Base URL must start with http:// or https://")


def _map_http_error(status: int, body: str) -> tuple[str, str, int]:
    """Map an HTTP status + provider body to (code, friendly message, status)."""
    snippet = body[:300].replace("\n", " ")
    if status in (401, 403):
        return (
            "invalid_api_key",
            "The provider rejected the API key. Check that the key is correct, "
            "has not expired, and has credit/permission for the selected model.",
            502,
        )
    if status == 402:
        return (
            "insufficient_credits",
            "The provider reports insufficient credits for this request. "
            "Top up the account or choose a different model.",
            502,
        )
    if status == 404:
        return (
            "model_not_found",
            "The provider returned 404. Usually this means the model name is "
            f"wrong or not available for your key. Provider said: {snippet}",
            502,
        )
    if status == 429:
        return (
            "provider_rate_limited",
            "The provider is rate-limiting requests. Wait a moment and try "
            "again, or reduce how often requests are sent.",
            502,
        )
    if status == 413:
        return ("request_too_large", "The request is too large for the provider.", 502)
    if status >= 500:
        return (
            "provider_outage",
            "The provider is having trouble right now (server error). "
            "Try again in a little while.",
            502,
        )
    if status == 400 and "context" in snippet.lower():
        return (
            "context_too_long",
            "The conversation grew too long for this model's context window. "
            "Start a new chat to continue.",
            502,
        )
    return ("bad_request", f"The provider rejected the request: {snippet}", 502)


async def test_connection(cfg: dict) -> dict:
    """Verify base URL + key (+ model when possible). Never returns the key."""
    base = cfg["base_url"].rstrip("/")
    headers = {
        "Authorization": f"Bearer {cfg['key']}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(20.0, connect=8.0)
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        # 1) List models - the standard OpenAI-compatible health endpoint.
        try:
            r = await client.get(f"{base}/models", headers=headers)
        except httpx.TimeoutException:
            return {"ok": False, "code": "network",
                    "message": "The connection timed out. Check the base URL and your internet connection."}
        except httpx.HTTPError as e:
            return {"ok": False, "code": "network",
                    "message": f"Could not reach the provider: {type(e).__name__}. Check the base URL."}

        if r.status_code in (401, 403):
            return {"ok": False, "code": "invalid_api_key",
                    "message": "The API key was rejected. Double-check the key value."}
        if r.status_code == 429:
            return {"ok": False, "code": "provider_rate_limited",
                    "message": "The provider is rate-limiting right now. Try again shortly."}
        if r.status_code >= 500:
            return {"ok": False, "code": "provider_outage",
                    "message": "The provider server is erroring. Try again later."}

        models: list[str] = []
        if r.status_code == 200:
            try:
                data = r.json()
                items = data.get("data", data) if isinstance(data, dict) else data
                models = [str(m.get("id", m)) if isinstance(m, dict) else str(m) for m in items]
            except (ValueError, TypeError):
                return {"ok": False, "code": "malformed_response",
                        "message": "The provider returned a response we could not parse."}
        elif r.status_code == 404:
            # Some compatible providers do not implement /models.
            # Fall back to a minimal chat completion to validate key + model.
            try:
                r2 = await client.post(
                    f"{base}/chat/completions",
                    headers=headers,
                    json={"model": cfg["model"], "messages": [{"role": "user", "content": "ping"}],
                          "max_tokens": 1},
                )
            except httpx.HTTPError as e:
                return {"ok": False, "code": "network",
                        "message": f"Could not reach the provider: {type(e).__name__}."}
            if r2.status_code != 200:
                code, msg, _ = _map_http_error(r2.status_code, r2.text)
                return {"ok": False, "code": code, "message": msg}
            return {"ok": True, "code": "ok",
                    "message": f"Connected to {cfg['model']} (this provider does not list models).",
                    "latency_ms": int((time.monotonic() - t0) * 1000), "models": []}

        model_known = cfg["model"] in models
        model_hint = ""
        if models and not model_known:
            model_hint = ("The model is not in the provider's model list, but some providers "
                          "still accept it. If chat fails, pick a model from the list.")
        return {
            "ok": True,
            "code": "ok",
            "message": f"Connected to {cfg['name'] or 'provider'} - {len(models)} models available.",
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "models": models[:200],
            "model_known": model_known,
            "model_hint": model_hint,
        }


async def stream_chat(
    cfg: dict,
    messages: list[dict],
    temperature: float = 0.4,
    max_tokens: int = 2048,
) -> AsyncIterator[str]:
    """Stream assistant deltas from an OpenAI-compatible provider."""
    base = cfg["base_url"].rstrip("/")
    headers = {
        "Authorization": f"Bearer {cfg['key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    timeout = httpx.Timeout(180.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            async with client.stream(
                "POST", f"{base}/chat/completions", headers=headers, json=payload
            ) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", "replace")
                    code, msg, status = _map_http_error(resp.status_code, body)
                    raise ProviderRequestError(code, msg, status)
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        return
                    try:
                        obj = json.loads(data)
                    except ValueError:
                        continue  # tolerate keep-alive or comment lines
                    if isinstance(obj, dict) and obj.get("error"):
                        err = obj["error"]
                        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                        raise ProviderRequestError("provider_error", str(msg)[:300])
                    for choice in obj.get("choices", []) if isinstance(obj, dict) else []:
                        delta = choice.get("delta") or {}
                        piece = delta.get("content")
                        if piece:
                            yield piece
        except httpx.ReadTimeout:
            raise ProviderRequestError(
                "timeout",
                "The AI provider took too long to respond. Try again, or use a faster model.",
                504,
            )
        except httpx.TimeoutException:
            raise ProviderRequestError(
                "timeout", "The connection to the AI provider timed out.", 504
            )
        except httpx.ConnectError:
            raise ProviderRequestError(
                "network",
                "Could not connect to the AI provider. Check the base URL and your connection.",
                502,
            )
        except httpx.HTTPError as e:
            raise ProviderRequestError(
                "network", f"Network error while contacting the provider: {type(e).__name__}.", 502
            )
