"""Sandboxed code execution endpoints.

Only Python is offered - and only because it genuinely runs in our isolated
runner. Languages without a working execution environment are NOT listed as
available (requirement: do not add a language unless its execution works).
"""
import asyncio
import platform

from fastapi import APIRouter, Request

from .. import db
from ..config import settings
from ..ratelimit import check_limit
from ..schemas import ExecRunIn
from ..services import execution
from ..services.progress import ensure_user, log_activity

router = APIRouter(prefix="/execution", tags=["execution"])


def _client_id(request: Request) -> str:
    return request.client.host if request.client else "local"


@router.get("/languages")
def languages():
    return {
        "languages": [{
            "id": "python",
            "label": "Python",
            "executable": True,
            "version": platform.python_version(),
            "timeout_seconds": settings.exec_timeout_default,
            "notes": "Runs in an isolated sandbox process with no network, "
                     "no secrets, and a hard time limit.",
        }]
    }


@router.post("/run")
async def run(body: ExecRunIn, request: Request):
    user = ensure_user()
    check_limit("execution", _client_id(request))
    _ = db

    result = await asyncio.to_thread(
        execution.run_python_sync, body.code, body.stdin or "",
        body.timeout or settings.exec_timeout_default,
    )
    log_activity(user["id"], "playground_run", "playground",
                 {"chars": len(body.code), "exit_code": result.exit_code,
                  "timed_out": result.timed_out})
    return result.to_dict()
