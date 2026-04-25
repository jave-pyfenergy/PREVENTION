# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Instalar dependencias de sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar pip-tools para resolución de dependencias
RUN pip install --no-cache-dir pip==24.0 hatchling

# Copiar manifesto de dependencias
COPY pyproject.toml ./

# Instalar dependencias de producción en /install
RUN pip install --no-cache-dir --prefix=/install \
    fastapi uvicorn[standard] gunicorn \
    pydantic pydantic-settings \
    supabase python-jose PyJWT \
    httpx google-cloud-secret-manager google-cloud-storage \
    scikit-learn xgboost numpy pandas \
    Pillow onnxruntime \
    python-multipart structlog \
    opentelemetry-api opentelemetry-sdk \
    opentelemetry-instrumentation-fastapi


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Seguridad: usuario no-root
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copiar dependencias instaladas
COPY --from=builder /install /usr/local

# Copiar código fuente
COPY app/ ./app/
COPY models/ ./models/

# Cambiar a usuario no-root
USER appuser

# Variables de entorno por defecto
ENV APP_ENV=production \
    LOG_LEVEL=INFO \
    PORT=8080 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8080

# Health check para Cloud Run
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Producción: gunicorn con workers uvicorn
CMD ["gunicorn", "app.entrypoints.api.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8080", \
     "--timeout", "30", \
     "--graceful-timeout", "10", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
