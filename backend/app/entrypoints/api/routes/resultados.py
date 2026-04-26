"""PrevencionApp — Routes: Resultados e Historial."""

from fastapi import APIRouter, HTTPException, Query, status

from app.application.dto.dtos import ResponseHistorial, ResponsePrediccion
from app.entrypoints.api.dependencies import CurrentUserId, HistorialDep
from app.config.container import get_container
from fastapi import Depends

router = APIRouter()


@router.get(
    "/resultado/{session_id}",
    response_model=ResponsePrediccion,
    status_code=status.HTTP_200_OK,
    summary="Obtener resultado por session_id",
)
async def obtener_resultado(
    session_id: str,
    container=Depends(get_container),
) -> ResponsePrediccion:
    evaluacion = await container.repositorio.obtener_evaluacion_por_session(session_id)
    if evaluacion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resultado no encontrado para session_id: {session_id}",
        )
    if evaluacion.esta_expirada():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="La evaluación ha expirado",
        )
    resultado = evaluacion.resultado
    if resultado is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resultado no disponible")

    return ResponsePrediccion(
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
