"""PrevencionApp — Routes: Resultados e Historial."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.application.dto.dtos import ResponseHistorial, ResponsePrediccion
from app.config.container import Container, get_container
from app.entrypoints.api.dependencies import CurrentUserId, HistorialDep
from app.infrastructure.cache.redis_client import RedisClient

router = APIRouter()

_CACHE_TTL = 300  # 5 minutos — menor que el TTL de la evaluación (24h)


def _get_redis(container: Annotated[Container, Depends(get_container)]) -> RedisClient:
    return container.redis


@router.get(
    "/resultado/{session_id}",
    response_model=ResponsePrediccion,
    status_code=status.HTTP_200_OK,
    summary="Obtener resultado por session_id",
)
async def obtener_resultado(
    session_id: str,
    container: Annotated[Container, Depends(get_container)],
    redis: Annotated[RedisClient, Depends(_get_redis)],
) -> ResponsePrediccion:
    cache_key = f"resultado:{session_id}"

    # Intentar desde Redis primero
    cached = await redis.get(cache_key)
    if cached:
        return ResponsePrediccion.model_validate_json(cached)

    evaluacion = await container.repositorio.obtener_evaluacion_por_session(session_id)
    if evaluacion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resultado no encontrado para session_id: {session_id}",
        )
    if evaluacion.esta_expirada():
        await redis.delete(cache_key)
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="La evaluación ha expirado",
        )
    resultado = evaluacion.resultado
    if resultado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resultado no disponible",
        )

    response = ResponsePrediccion(
        evaluacion_id=evaluacion.id,
        session_id=evaluacion.session_id,
        nivel_inflamacion=resultado.nivel_riesgo.value,
        probabilidad=resultado.probabilidad,
        confianza=resultado.confianza,
        es_confiable=resultado.es_confiable,
        gradcam_url=resultado.gradcam_url,
        recomendacion=resultado.recomendacion(),
        features_importantes=resultado.features_importantes,
        fecha=evaluacion.fecha_creacion,
    )

    # Guardar en cache para requests subsecuentes
    await redis.setex(cache_key, _CACHE_TTL, response.model_dump_json())

    return response


@router.get(
    "/historial",
    response_model=ResponseHistorial,
    status_code=status.HTTP_200_OK,
    summary="Historial de evaluaciones (requiere JWT)",
)
async def obtener_historial(
    user_id: CurrentUserId,
    historial: HistorialDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ResponseHistorial:
    return await historial.ejecutar(user_id, page, page_size)
