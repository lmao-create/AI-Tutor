"""AI provider settings and user preferences.

Security: the API key is write-only. GET endpoints return a masked form,
the raw key never appears in any response body.
"""
from fastapi import APIRouter, Request, status

from .. import db, secrets
from ..errors import AppError
from ..ratelimit import check_limit
from ..schemas import PreferencesIn, ProviderConfigIn, ProviderTestIn
from ..services import ai
from ..services.progress import ensure_user

router = APIRouter(prefix="/settings", tags=["settings"])


def _client_id(request: Request) -> str:
    return request.client.host if request.client else "local"


def _masked_view() -> dict:
    cfg = ai.get_provider_config()
    if cfg is None:
        return {"configured": False, "source": None, "provider_name": None,
                "base_url": None, "model": None, "key_masked": None}
    return {
        "configured": bool(cfg["key"]),
        "source": cfg["source"],
        "provider_name": cfg["name"],
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "key_masked": secrets.mask_key(cfg["key"]),
    }


@router.get("/provider")
def get_provider():
    return _masked_view()


@router.put("/provider")
def save_provider(body: ProviderConfigIn):
    existing = db.query_one("SELECT id FROM provider_config WHERE id = 1")

    if body.api_key is not None:
        if body.api_key.strip() == "":
            secrets.clear_stored_key()   # explicit empty string clears the key
        else:
            secrets.set_stored_key(body.api_key.strip())

    if existing:
        db.execute(
            "UPDATE provider_config SET provider_name = ?, base_url = ?, "
            "model = ?, updated_at = datetime('now') WHERE id = 1",
            (body.provider_name, body.base_url, body.model),
        )
    else:
        db.execute(
            "INSERT INTO provider_config (id, provider_name, base_url, model) "
            "VALUES (1, ?, ?, ?)",
            (body.provider_name, body.base_url, body.model),
        )
    return _masked_view()


@router.post("/provider/test")
async def test_provider(request: Request,
                        body: ProviderTestIn | None = None):
    check_limit("ai_test", _client_id(request))
    body = body or ProviderTestIn()

    stored = ai.get_provider_config() or {}
    draft_present = any([body.provider_name, body.base_url, body.model,
                         body.api_key])
    if draft_present:
        # Testing a draft from the Settings form. Fall back per-field to
        # stored values so the user can test just the model change, etc.
        key = (body.api_key or "").strip() or stored.get("key")
        cfg = {
            "name": (body.provider_name or "").strip()
                    or stored.get("name") or "Provider",
            "base_url": (body.base_url or "").strip()
                        or stored.get("base_url", ""),
            "model": (body.model or "").strip() or stored.get("model", ""),
        }
    else:
        cfg = dict(stored)
        key = stored.get("key")
        if not cfg:
            raise AppError(400, "no_provider",
                            "No AI provider is configured. Enter a base URL, "
                            "model and API key first.")

    if not (cfg.get("base_url") and cfg.get("model")):
        raise AppError(400, "incomplete_provider",
                        "Base URL and model are required to test a connection.")
    if not key:
        raise AppError(400, "no_provider",
                        "No API key is set. Enter a key first, or configure "
                        "CODETUTOR_API_KEY in the environment.")

    result = await ai.test_connection({**cfg, "key": key})
    return result


@router.delete("/provider")
def clear_provider():
    db.execute("DELETE FROM provider_config WHERE id = 1")
    secrets.clear_stored_key()
    return _masked_view()


@router.get("/preferences")
def get_preferences(request: Request):
    user = ensure_user()
    _ = request
    row = db.query_one("SELECT * FROM preferences WHERE user_id = ?", (user["id"],))
    if row is None:
        db.execute("INSERT INTO preferences (user_id) VALUES (?)", (user["id"],))
        row = db.query_one("SELECT * FROM preferences WHERE user_id = ?", (user["id"],))
    return {
        "theme": row["theme"],
        "active_course": row["active_course"],
        "default_tutor_mode": row["default_tutor_mode"],
        "editor_font_size": row["editor_font_size"],
    }


@router.put("/preferences")
def save_preferences(body: PreferencesIn, request: Request):
    user = ensure_user()
    _ = request
    current = db.query_one("SELECT * FROM preferences WHERE user_id = ?", (user["id"],))
    if current is None:
        db.execute("INSERT INTO preferences (user_id) VALUES (?)", (user["id"],))
        current = db.query_one("SELECT * FROM preferences WHERE user_id = ?", (user["id"],))

    db.execute(
        "UPDATE preferences SET theme = ?, active_course = ?, "
        "default_tutor_mode = ?, editor_font_size = ?, "
        "updated_at = datetime('now') WHERE user_id = ?",
        (
            body.theme or current["theme"],
            body.active_course or current["active_course"],
            body.default_tutor_mode or current["default_tutor_mode"],
            body.editor_font_size or current["editor_font_size"],
            user["id"],
        ),
    )
    return status.HTTP_200_OK and {
        "theme": body.theme or current["theme"],
        "active_course": body.active_course or current["active_course"],
        "default_tutor_mode": body.default_tutor_mode or current["default_tutor_mode"],
        "editor_font_size": body.editor_font_size or current["editor_font_size"],
    }
