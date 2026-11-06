"""API-level tests: conversations, chat wiring, limits, error shapes."""
import json

# Captured before any test patches httpx.AsyncClient (mock transport).
import httpx

_REAL_ASYNC_CLIENT = httpx.AsyncClient


def test_conversation_crud(client):
    r = client.post("/api/conversations", json={"mode": "learn"})
    assert r.status_code == 201
    conv = r.json()
    cid = conv["id"]

    r = client.get("/api/conversations")
    assert r.status_code == 200
    assert any(c["id"] == cid for c in r.json()["conversations"])

    r = client.patch(f"/api/conversations/{cid}", json={"title": "My chat"})
    assert r.json()["title"] == "My chat"

    r = client.delete(f"/api/conversations/{cid}")
    assert r.status_code == 204
    r = client.get(f"/api/conversations/{cid}")
    assert r.status_code == 404


def test_chat_without_provider_returns_clear_error(client):
    cid = client.post("/api/conversations", json={"mode": "learn"}).json()["id"]
    r = client.post(f"/api/conversations/{cid}/chat",
                    json={"content": "What is a variable?"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "no_provider"
    # The offline lessons still work while chat is unavailable
    assert client.get("/api/courses").status_code == 200


def test_chat_persists_user_message_even_in_demo_mode(client):
    cid = client.post("/api/conversations", json={"mode": "learn"}).json()["id"]
    client.post(f"/api/conversations/{cid}/chat", json={"content": "hi"})
    msgs = client.get(f"/api/conversations/{cid}").json()["messages"]
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"


def test_chat_with_mocked_provider_streams_and_persists(client, monkeypatch):
    body = "\n".join([
        'data: ' + json.dumps({"choices": [{"delta": {"content": "Teach"}}]}),
        'data: ' + json.dumps({"choices": [{"delta": {"content": " mode"}}]}),
        'data: [DONE]',
    ]) + "\n"

    def factory(*args, **kwargs):
        kwargs.pop("timeout", None)
        return _REAL_ASYNC_CLIENT(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(200, text=body)))
    monkeypatch.setattr(httpx, "AsyncClient", factory)

    client.put("/api/settings/provider", json={
        "provider_name": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "meta/llama-3.3-70b-instruct",
        "api_key": "nvapi-12345678"})

    cid = client.post("/api/conversations", json={"mode": "learn"}).json()["id"]
    r = client.post(f"/api/conversations/{cid}/chat",
                    json={"content": "Teach me variables"})
    assert r.status_code == 200
    assert "data:" in r.text
    assert '"delta"' in r.text

    # both messages persisted; title taken from the first user message
    conv = client.get(f"/api/conversations/{cid}").json()
    assert conv["title"] == "Teach me variables"
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant"]
    assert conv["messages"][1]["content"] == "Teach mode"


def test_retry_after_error(client, monkeypatch):
    def factory(*args, **kwargs):
        kwargs.pop("timeout", None)
        return _REAL_ASYNC_CLIENT(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(502, text="bad gateway")))
    monkeypatch.setattr(httpx, "AsyncClient", factory)

    client.put("/api/settings/provider", json={
        "provider_name": "X", "base_url": "https://x/v1", "model": "m",
        "api_key": "sk-1234567890"})

    cid = client.post("/api/conversations", json={}).json()["id"]
    r = client.post(f"/api/conversations/{cid}/chat",
                    json={"content": "hello"})
    assert r.status_code == 200  # SSE started; error event inside
    assert "provider_outage" in r.text

    # Now fix the provider and retry the last question
    body = 'data: ' + json.dumps(
        {"choices": [{"delta": {"content": "recovered"}}]}) + "\ndata: [DONE]\n"

    def factory2(*args, **kwargs):
        kwargs.pop("timeout", None)
        return _REAL_ASYNC_CLIENT(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(200, text=body)))
    monkeypatch.setattr(httpx, "AsyncClient", factory2)

    r = client.post(f"/api/conversations/{cid}/retry")
    assert r.status_code == 200
    assert '"delta"' in r.text
    msgs = client.get(f"/api/conversations/{cid}").json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["content"] == "recovered"


def test_body_size_limit(client):
    big = "x" * 70000
    r = client.post("/api/execution/run",
                    json={"language": "python", "code": big})
    # 70k chars exceeds max_code_chars (60k) -> validation or 413
    assert r.status_code in (400, 413)


def test_validation_error_shape(client):
    r = client.post("/api/conversations", json={"mode": "not_a_mode"})
    assert r.status_code == 400
    err = r.json()["error"]
    assert err["code"] == "validation_error"
    assert "mode" in err["message"]


def test_404_for_unknown_route_returns_error_shape(client):
    r = client.get("/api/definitely-not-a-route")
    assert r.status_code in (404, 405)


def test_exercise_submission_endpoints(client):
    # mcq exercise id 1 (what-is-programming-ex), correct answer index 2
    r = client.post("/api/exercises/1/submit", json={"choice": 2})
    assert r.status_code == 200
    data = r.json()
    assert data["passed"] is True
    assert data["status"]["attempts"] == 1
    assert data["status"]["passed"] is True
    assert data["feedback"]["answer_index"] == 2  # revealed after earning it

    r = client.post("/api/exercises/1/submit", json={"choice": 0})
    data = r.json()
    assert data["passed"] is False
    assert "answer_index" not in data["feedback"]  # hidden while unearned


def test_preferences_roundtrip(client):
    r = client.get("/api/settings/preferences")
    assert r.status_code == 200
    assert r.json()["theme"] == "dark"

    r = client.put("/api/settings/preferences",
                   json={"theme": "light", "editor_font_size": 16})
    assert r.status_code == 200
    assert r.json()["theme"] == "light"

    r = client.put("/api/settings/preferences", json={"editor_font_size": 99})
    assert r.status_code == 400


def test_demo_mode_health_flag(client):
    data = client.get("/api/health").json()
    assert data["demo_mode"] is True
    client.put("/api/settings/provider", json={
        "provider_name": "X", "base_url": "https://x/v1", "model": "m",
        "api_key": "sk-1"})
    data = client.get("/api/health").json()
    assert data["demo_mode"] is False
    assert data["provider_configured"] is True


def test_tools_without_provider(client):
    r = client.post("/api/tools/explain",
                    json={"code": "x = 1", "mode": "explain"})
    assert r.status_code == 409
    r = client.post("/api/tools/debug", json={"code": "x = 1"})
    assert r.status_code == 409


def test_tools_invalid_mode(client):
    r = client.post("/api/tools/explain",
                    json={"code": "x = 1", "mode": "nonexistent"})
    assert r.status_code == 400
