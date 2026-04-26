"""PrevencionApp — Routes: Evaluación y Subida de Imágenes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.application.dto.dtos import RequestFormulario, ResponsePrediccion, ResponseSignedUrl
from app.application.dto.dtos import RequestVincularEvaluacion
from app.config.container import get_container
from app.config.settings import get_settings
from app.entrypoints.api.dependencies import (
    CurrentUserId,
    PredecirDep,
    VincularDep,
    get_storage,
)
from app.entrypoints.api.limiter import limiter as _limiter
from app.infrastructure.storage.supabase_storage_adapter import (
    BUCKET_TEMP,
    SupabaseStorageAdapter,
)

router = APIRouter()
_settings = get_settings()
_RATE_LIMIT = f"{_settings.rate_limit_per_hour}/hour"


@router.post(
    "/evaluacion-temporal",
    response_model=ResponsePrediccion,
    status_code=status.HTTP_200_OK,
    summary="Ejecutar evaluación clínica (flujo anónimo)",
    description=(
        "Recibe formulario clínico + URL de imagen opcional. "
        "Ejecuta inferencia ML y retorna el resultado. "
        "No requiere autenticación."
    ),
)
@_limiter.limit(_RATE_LIMIT)
async def crear_evaluacion_temporal(
    request: Request,
    formulario: RequestFormulario,
    predecir: PredecirDep,
) -> ResponsePrediccion:
    return await predecir.ejecutar(formulario)


@router.post(
    "/imagenes/upload-url",
    response_model=ResponseSignedUrl,
    status_code=status.HTTP_200_OK,
    summary="Obtener Signed URL para subida de imagen",
    description=(
        "Genera un Signed URL de subida válido por 5 minutos. "
        "El cliente sube directamente a Supabase Storage. "
        "El tráfico NO pasa por la API."
    ),
)
async def obtener_upload_url(
    storage: SupabaseStorageAdapter = Depends(get_storage),
) -> ResponseSignedUrl:
    filename = f"{uuid.uuid4()}.jpg"
    path = f"temp/{filename}"

    try:
        signed_url = await storage.generar_signed_url_subida(
            bucket=BUCKET_TEMP,
            path=path,
            ttl_seconds=300,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Servicio de almacenamiento no disponible: {exc}",
        ) from exc
    return ResponseSignedUrl(signed_url=signed_url, path=path, ttl_seconds=300)


@router.post(
    "/vincular-evaluacion",
    status_code=status.HTTP_200_OK,
    summary="Vincular evaluación anónima al usuario autenticado",
)
async def vincular_evaluacion(
    evaluacion_id: uuid.UUID,
    user_id: CurrentUserId,
    vincular: VincularDep,
) -> dict:
    request = RequestVincularEvaluacion(
        evaluacion_id=evaluacion_id,
        user_id=user_id,
    )
    await vincular.ejecutar(request)
    return {"ok": True}
