"""
PrevencionApp — FastAPI Application Entry Point.
Configuración de middleware, CORS, OpenTelemetry y manejo de errores.
"""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.container import get_container
from app.entrypoints.api.limiter import limiter
from app.config.settings import get_settings
from app.entrypoints.api.routes import formulario, paciente, resultados
from app.domain.services.evaluador_clinico import (
    ConsentimientoRequeridoError,
    DomainValidationError,
)

_MAX_BODY_BYTES = 1 * 1024 * 1024  # 1 MB

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
    logger.info("app_iniciando", env=settings.app_env, version="1.0.0")

    container = get_container()

    # Conectar Redis antes de recibir tráfico
    await container.redis.connect()

    # Restaurar estado del detector de drift desde Redis (sobrevive reinicios)
    await container.drift_detector.restaurar_desde_redis(container.redis)

    # Pre-warm modelo ML — evita cold-start en la primera evaluación
    try:
        container.ml_model.cargar_modelo()
        logger.info("modelo_ml_precargado")
    except Exception as exc:
        logger.warning("modelo_ml_precarga_fallida", error=str(exc))

    logger.info("contenedor_di_listo")

    yield

    # Persistir estado del detector de drift antes de cerrar
    await container.drift_detector.persistir_en_redis(container.redis)
    await container.redis.close()
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

# ── Rate limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    max_age=600,
)


# ── Security headers ──────────────────────────────────────────────────────────
class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path.startswith(settings.api_v1_prefix):
            response.headers["Cache-Control"] = "no-store"
        return response


app.add_middleware(_SecurityHeadersMiddleware)


# ── Body size limit ───────────────────────────────────────────────────────────
class _BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_BODY_BYTES:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"error": "payload_too_large", "message": "El cuerpo de la solicitud supera 1 MB"},
            )
        return await call_next(request)


app.add_middleware(_BodySizeLimitMiddleware)


# ── Middleware de auditoría clínica ───────────────────────────────────────────
@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    """
    Registra todas las operaciones con contexto clínico de auditoría.
    Cumplimiento: GDPR Art.30 (registro de actividades), HIPAA §164.312.
    """
    start = time.perf_counter()
    request_id = request.headers.get("X-Request-ID", "")

    # Extraer user_id del JWT de forma no bloqueante (solo para auditoría)
    user_id: str | None = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            import jwt as _jwt
            token = auth_header.removeprefix("Bearer ").strip()
            payload = _jwt.decode(token, options={"verify_signature": False})
            user_id = payload.get("sub")
        except Exception:
            pass

    response = await call_next(request)

    duration_ms = (time.perf_counter() - start) * 1000
    is_data_op = request.method in ("POST", "PUT", "PATCH", "DELETE")

    log_fn = logger.warning if response.status_code >= 400 else logger.info
    log_fn(
        "audit",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round(duration_ms, 2),
        request_id=request_id,
        user_id=user_id,
        ip=request.client.host if request.client else None,
        data_operation=is_data_op,
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
async def health_check(container=Depends(get_container)):
    import uuid as _uuid

    checks: dict[str, str] = {}

    # Database
    try:
        await container.repositorio.obtener_paciente(
            _uuid.UUID("00000000-0000-0000-0000-000000000000")
        )
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    # ML model
    checks["ml_model"] = "ok" if container.ml_model.esta_disponible() else "unavailable"

    # Redis (opcional — degraded, no error)
    checks["redis"] = "ok" if container.redis.is_available else "unavailable"

    critical_failing = checks["database"] == "error"
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE if critical_failing else status.HTTP_200_OK,
        content={
            "status": "error" if critical_failing else "ok",
            "version": "1.0.0",
            "env": settings.app_env,
            "checks": checks,
        },
    )
