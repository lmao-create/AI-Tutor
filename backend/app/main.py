"""CodeTutor AI - FastAPI application factory."""
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, db
from .config import settings
from .errors import AppError
from .routers import (conversations, courses, execution, exercises, health,
                      projects, progress, settings as settings_router, tools)
from .seed import seed_all
from .services.progress import ensure_user


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize schema + seed offline content on every startup (idempotent).
    db.get_conn()
    db_migrations_ok = True
    try:
        stats = seed_all()
        ensure_user()
    except Exception as e:  # pragma: no cover - defensive: never crash startup
        db_migrations_ok = False
        print(f"[codetutor] WARNING: content seeding failed: {e}")
    else:
        print(f"[codetutor] Content ready: {stats}")
    yield
    db.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.app_name} API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173", "http://127.0.0.1:5173",
            f"http://localhost:{settings.port}", f"http://127.0.0.1:{settings.port}",
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def limit_body_size(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() \
                and int(content_length) > settings.max_body_bytes:
            return JSONResponse(
                status_code=413,
                content={"error": {"code": "payload_too_large",
                                   "message": "Request body is too large."}},
            )
        return await call_next(request)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        headers = {}
        if getattr(exc, "retry_after", None):
            headers["Retry-After"] = str(exc.retry_after)
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message}},
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request,
                                       exc: RequestValidationError):
        from fastapi.encoders import jsonable_encoder
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", [])[1:]) or "body"
        msg = first.get("msg", "invalid input")
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "validation_error",
                               "message": f"Invalid {field}: {msg}",
                               "details": jsonable_encoder(exc.errors())[:10]}},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error",
                               "message": "An unexpected error occurred. "
                                          "Check the server logs for details."}},
        )

    app.include_router(health.router, prefix="/api")
    app.include_router(settings_router.router, prefix="/api")
    app.include_router(conversations.router, prefix="/api")
    app.include_router(courses.router, prefix="/api")
    app.include_router(exercises.router, prefix="/api")
    app.include_router(execution.router, prefix="/api")
    app.include_router(tools.router, prefix="/api")
    app.include_router(progress.router, prefix="/api")
    app.include_router(projects.router, prefix="/api")

    # Serve the built frontend (frontend/dist) when present, so the whole app
    # can run from the backend alone in "production" mode. This handler also
    # serves index.html for unknown paths so deep links (e.g. /learn/python)
    # work like they do under the Vite dev server.
    dist = settings.root / "frontend" / "dist"
    if dist.exists():
        from fastapi.responses import FileResponse

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            if full_path.startswith("api/"):
                raise AppError(404, "not_found", "API endpoint not found.")
            candidate = (dist / full_path).resolve()
            try:
                candidate.relative_to(dist.resolve())
            except ValueError:
                raise AppError(404, "not_found", "Not found.")
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")
    else:
        @app.get("/", include_in_schema=False)
        def root():
            return {"app": settings.app_name,
                    "version": __version__,
                    "hint": "Run the Vite dev server (frontend/) for the UI, "
                            "or build it with `npm run build`."}

    return app


app = create_app()
