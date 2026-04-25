"""
PrevencionApp — FastAPI Application Entry Point.
Configuración de middleware, CORS, OpenTelemetry y manejo de errores.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.container import get_container
from app.config.settings import get_settings
from app.entrypoints.api.routes import formulario, paciente, resultados
from app.domain.services.evaluador_clinico import (
    ConsentimientoRequeridoError,
    DomainValidationError,
)

# ── Logging estructurado ──────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Inicialización y teardown de la aplicación."""
    logger.info("PrevencionApp iniciando", env=settings.app_env, version="1.0.0")

    # Pre-warm el contenedor DI (carga modelos, conecta DB)
    container = get_container()
    logger.info("Contenedor DI inicializado")

    yield

    logger.info("PrevencionApp cerrando")


app = FastAPI(
    title="PrevencionApp API",
    description=(
        "Plataforma de telemedicina preventiva para detección temprana "
        "de inflamación sinovial mediante análisis clínico y visual con ML."
    ),
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    max_age=600,
)


# ── Middleware de telemetría ───────────────────────────────────────────────────
@app.middleware("http")
async def telemetria_middleware(request: Request, call_next):
    start = time.perf_counter()
    request_id = request.headers.get("X-Request-ID", "")

    response = await call_next(request)

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round(duration_ms, 2),
        request_id=request_id,
    )
    response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
    return response


# ── Manejadores de errores de dominio ─────────────────────────────────────────
@app.exception_handler(DomainValidationError)
async def domain_validation_handler(request: Request, exc: DomainValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "domain_validation_error", "message": str(exc)},
    )


@app.exception_handler(ConsentimientoRequeridoError)
async def consentimiento_handler(request: Request, exc: ConsentimientoRequeridoError):
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"error": "consentimiento_requerido", "message": str(exc)},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
API_PREFIX = settings.api_v1_prefix

app.include_router(formulario.router, prefix=API_PREFIX, tags=["Evaluación"])
app.include_router(resultados.router, prefix=API_PREFIX, tags=["Resultados"])
app.include_router(paciente.router, prefix=API_PREFIX, tags=["Paciente"])


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Infrastructure"], include_in_schema=False)
async def health_check():
    return {"status": "ok", "version": "1.0.0", "env": settings.app_env}
