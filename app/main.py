import logging
import re
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routers import auth, chat_messages, document_processing, documents, knowledge_bases, rag
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import get_engine
from app.services.rag import get_vector_store
from app.services.auth import bootstrap_admin, get_current_user

configure_logging(get_settings().log_level)
logger = logging.getLogger("repomind.access")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if bootstrap_admin():
        logger.info("bootstrap_admin_created")
    yield

app = FastAPI(
    title="RepoMind API",
    description="面向后端项目文档的知识库助手",
    version="0.1.0",
    lifespan=lifespan,
)


def _request_id(value: str | None) -> str:
    if value and re.fullmatch(r"[A-Za-z0-9-]{1,64}", value):
        return value
    return uuid4().hex


def _check_dependencies_ready() -> dict[str, str]:
    settings = get_settings()
    components: dict[str, str] = {}

    try:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not configured")
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        components["database"] = "ok"
    except Exception:
        components["database"] = "unavailable"

    try:
        get_vector_store()
        components["vector_store"] = "ok"
    except Exception:
        components["vector_store"] = "unavailable"

    components["llm_configuration"] = "ok" if settings.deepseek_api_key else "incomplete"
    components["auth_configuration"] = "ok" if settings.jwt_secret_key else "incomplete"
    return components


@app.middleware("http")
async def log_request(request: Request, call_next):
    request_id = _request_id(request.headers.get("X-Request-ID"))
    started_at = perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception(
            "request_failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
                "latency_ms": round((perf_counter() - started_at) * 1000),
                "error_type": type(exc).__name__,
            },
        )
        raise
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": round((perf_counter() - started_at) * 1000),
        },
    )
    return response


@app.get("/health")
async def health_check():
    return {"status": "ok", "project": "RepoMind"}


@app.get("/ready")
async def readiness_check(request: Request):
    probe = getattr(request.app.state, "readiness_probe", _check_dependencies_ready)
    try:
        components = probe()
    except Exception as exc:
        logger.warning(
            "readiness_check_failed",
            extra={"path": "/ready", "status_code": 503, "error_type": type(exc).__name__},
        )
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "components": {"database": "unavailable"}},
        )
    if components is None:
        components = {"database": "ok", "vector_store": "ok", "configuration": "ok"}
    if all(value == "ok" for value in components.values()):
        return {"status": "ready", "components": components}
    logger.warning("readiness_check_failed", extra={"path": "/ready", "status_code": 503})
    return JSONResponse(status_code=503, content={"status": "not_ready", "components": components})


app.include_router(auth.router)
protected_dependencies = [Depends(get_current_user)]
app.include_router(knowledge_bases.router, dependencies=protected_dependencies)
app.include_router(documents.router, dependencies=protected_dependencies)
app.include_router(chat_messages.router, dependencies=protected_dependencies)
app.include_router(document_processing.document_router, dependencies=protected_dependencies)
app.include_router(document_processing.task_router, dependencies=protected_dependencies)
app.include_router(rag.router, dependencies=protected_dependencies)
