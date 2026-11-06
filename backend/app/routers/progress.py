"""Learning progress dashboard and reset."""
from fastapi import APIRouter, status

from ..errors import AppError
from ..schemas import ResetIn
from ..services.progress import dashboard, ensure_user, reset_progress

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("")
def get_progress():
    user = ensure_user()
    return dashboard(user["id"])


@router.post("/reset")
def reset(body: ResetIn):
    user = ensure_user()
    if body.confirm is not True:
        raise AppError(400, "confirm_required",
                       "Resetting progress requires confirm: true.")
    reset_progress(user["id"])
    return {"reset": True}
