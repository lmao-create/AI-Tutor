"""Health check + basic app info."""
from fastapi import APIRouter

from .. import db, __version__
from ..config import settings
from ..services import ai

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    db_ok = True
    try:
        db.query_one("SELECT 1 AS ok")
    except Exception:
        db_ok = False

    cfg = ai.get_provider_config()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": __version__,
        "db_ok": db_ok,
        "provider_configured": bool(cfg and cfg["key"]),
        "demo_mode": not bool(cfg and cfg["key"]),
        "provider": {"name": cfg["name"], "model": cfg["model"]} if cfg else None,
    }


@router.get("/tutor/modes")
def tutor_modes():
    from ..services.tutor import available_modes
    return {"modes": available_modes()}
