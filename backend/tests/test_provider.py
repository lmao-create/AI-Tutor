"""AI provider tests: config storage, masking, connection tests, streaming,
and error mapping - all against a mocked HTTP transport (no real network)."""
import json

import httpx
import pytest

from app.errors import ProviderNotConfiguredError, ProviderRequestError
from app.services import ai


# Capture the real class BEFORE any test patches httpx.AsyncClient.
_REAL_ASYNC_CLIENT = httpx.AsyncClient

CFG = {"name": "NVIDIA NIM", "base_url": "https://integrate.api.nvidia.com/v1",
       "model": "meta/llama-3.3-70b-instruct", "key": "nvapi-SECRET-12345678",
       "source": "settings"}


# ---------------------------------------------------------------------------
# Config resolution + secret hygiene
# ---------------------------------------------------------------------------
def test_no_provider_by_default(fresh_db):
    assert ai.get_provider_config() is None
    with pytest.raises(ProviderNotConfiguredError):
        ai.require_provider_config()


def test_provider_config_roundtrip_never_leaks_key(client):
    r = client.put("/api/settings/provider", json={
        "provider_name": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "meta/llama-3.3-70b-instruct",
        "api_key": "nvapi-SECRET-12345678",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["configured"] is True
    assert data["key_masked"].startswith("nvapi")
    assert data["key_masked"].endswith("5678")
    assert "SECRET-12345678" not in r.text          # raw key never in response
    assert data["base_url"] == "https://integrate.api.nvidia.com/v1"

    # GET gives the same masked view
    r2 = client.get("/api/settings/provider")
    assert "SECRET-12345678" not in r2.text
    assert r2.json()["model"] == "meta/llama-3.3-70b-instruct"


def test_saving_without_key_keeps_existing(client):
    client.put("/api/settings/provider", json={
        "provider_name": "P", "base_url": "https://x.example/v1",
        "model": "m1", "api_key": "sk-first-12345678"})
    # api_key omitted entirely -> key preserved
    r = client.put("/api/settings/provider", json={
        "provider_name": "P", "base_url": "https://x.example/v1", "model": "m2"})
    assert r.status_code == 200
    data = r.json()
    assert data["configured"] is True
    assert data["model"] == "m2"
    # empty string clears it
    r = client.put("/api/settings/provider", json={
        "provider_name": "P", "base_url": "https://x.example/v1", "model": "m2",
        "api_key": ""})
    assert r.json()["configured"] is False


def test_invalid_base_url_rejected(client):
    r = client.put("/api/settings/provider", json={
        "provider_name": "X", "base_url": "ftp://nope", "model": "m"})
    assert r.status_code == 400
    r = client.put("/api/settings/provider", json={
        "provider_name": "   ", "base_url": "https://x/v1", "model": "m"})
    assert r.status_code == 400


def test_env_provider_fallback(monkeypatch, fresh_db):
    from app.config import settings
    monkeypatch.setattr(settings, "env_provider", {
        "name": "Groq", "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile", "key": "gsk-abc"})
    cfg = ai.get_provider_config()
    assert cfg["source"] == "env"
    assert cfg["name"] == "Groq"
    ai.require_provider_config()  # no raise


def test_delete_provider_config(client):
    client.put("/api/settings/provider", json={
        "provider_name": "P", "base_url": "https://x/v1", "model": "m",
        "api_key": "sk-123456789"})
    r = client.delete("/api/settings/provider")
    assert r.status_code == 200
    assert r.json()["configured"] is False


# ---------------------------------------------------------------------------
# Connection test with mocked transport
# ---------------------------------------------------------------------------
def _mock(monkeypatch, handler):
    def factory(*args, **kwargs):
        kwargs.pop("timeout", None)
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(httpx, "AsyncClient", factory)


def test_connection_test_success(client, monkeypatch):
    def handler(request):
        assert request.url.path.endswith("/models")
        assert request.headers["authorization"] == "Bearer nvapi-test"
        return httpx.Response(200, json={"data": [
            {"id": "meta/llama-3.3-70b-instruct"},
            {"id": "deepseek-ai/deepseek-r1"}]})

    client.put("/api/settings/provider", json={
        "provider_name": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "meta/llama-3.3-70b-instruct",
        "api_key": "nvapi-test"})
    _mock(monkeypatch, handler)
    r = client.post("/api/settings/provider/test")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["model_known"] is True
    assert len(data["models"]) == 2


def test_connection_test_invalid_key(client, monkeypatch):
    def handler(request):
        return httpx.Response(401, json={"error": "bad key"})
    client.put("/api/settings/provider", json={
        "provider_name": "X", "base_url": "https://x/v1", "model": "m",
        "api_key": "sk-wrong"})
    _mock(monkeypatch, handler)
    r = client.post("/api/settings/provider/test")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is False
    assert data["code"] == "invalid_api_key"


def test_connection_test_rate_limit_and_outage(client, monkeypatch):
    client.put("/api/settings/provider", json={
        "provider_name": "X", "base_url": "https://x/v1", "model": "m",
        "api_key": "sk-1"})

    _mock(monkeypatch, lambda req: httpx.Response(429, json={"error": "slow"}))
    data = client.post("/api/settings/provider/test").json()
    assert data["code"] == "provider_rate_limited"

    _mock(monkeypatch, lambda req: httpx.Response(503, json={"error": "down"}))
    data = client.post("/api/settings/provider/test").json()
    assert data["code"] == "provider_outage"


def test_connection_test_without_key(client):
    r = client.post("/api/settings/provider/test")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "no_provider"


# ---------------------------------------------------------------------------
# Streaming chat with mocked SSE
# ---------------------------------------------------------------------------
def _sse(lines):
    return "\n".join(lines) + "\n"


def test_stream_chat_happy_path(monkeypatch):
    body = _sse([
        'data: ' + json.dumps({"choices": [{"delta": {"content": "Hello "}}]}),
        'data: ' + json.dumps({"choices": [{"delta": {"content": "world"}}]}),
        'data: [DONE]',
    ])

    async def run():
        _mock(monkeypatch, lambda req: httpx.Response(200, text=body))
        out = []
        async for piece in ai.stream_chat(CFG, [{"role": "user",
                                                 "content": "hi"}]):
            out.append(piece)
        return out

    import asyncio
    assert asyncio.run(run()) == ["Hello ", "world"]


def test_stream_chat_malformed_lines_ignored(monkeypatch):
    body = _sse([
        ': keep-alive comment',
        'data: not json at all',
        'data: ' + json.dumps({"choices": [{"delta": {"content": "ok"}}]}),
        'data: [DONE]',
    ])
    async def run():
        _mock(monkeypatch, lambda req: httpx.Response(200, text=body))
        out = []
        async for piece in ai.stream_chat(CFG, []):
            out.append(piece)
        return out
    import asyncio
    assert asyncio.run(run()) == ["ok"]


def test_stream_chat_maps_http_errors(monkeypatch):
    cases = [
        (401, "invalid_api_key"),
        (402, "insufficient_credits"),
        (404, "model_not_found"),
        (429, "provider_rate_limited"),
        (500, "provider_outage"),
    ]
    import asyncio
    for status, expected in cases:
        _mock(monkeypatch, lambda req, s=status: httpx.Response(
            s, json={"error": {"message": "boom"}}))
        async def run():
            try:
                async for _ in ai.stream_chat(CFG, []):
                    pass
                return None
            except ProviderRequestError as e:
                return e.code
        assert asyncio.run(run()) == expected


def test_stream_chat_error_object_in_stream(monkeypatch):
    body = _sse([
        'data: ' + json.dumps({"error": {"message": "context too long"}}),
    ])
    async def run():
        _mock(monkeypatch, lambda req: httpx.Response(200, text=body))
        try:
            async for _ in ai.stream_chat(CFG, []):
                pass
            return None
        except ProviderRequestError as e:
            return e.code
    import asyncio
    assert asyncio.run(run()) == "provider_error"


def test_stream_chat_network_failure(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("no route to host")

    async def run():
        _mock(monkeypatch, handler)
        try:
            async for _ in ai.stream_chat(CFG, []):
                pass
            return None
        except ProviderRequestError as e:
            return e.code
    import asyncio
    assert asyncio.run(run()) == "network"
