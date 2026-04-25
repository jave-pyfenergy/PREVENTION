"""PrevencionApp — Routes: Paciente."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status, Depends

from app.application.dto.dtos import PacienteDTO, RequestRegistrarPaciente
from app.entrypoints.api.dependencies import CurrentUserId, RegistrarDep
from app.config.container import get_container

router = APIRouter()


@router.get(
    "/paciente/perfil",
    response_model=PacienteDTO,
    status_code=status.HTTP_200_OK,
    summary="Obtener perfil del paciente autenticado",
)
async def obtener_perfil(
    user_id: CurrentUserId,
    container=Depends(get_container),
) -> PacienteDTO:
    paciente = await container.repositorio.obtener_paciente(user_id)
    if paciente is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfil de paciente no encontrado",
        )
    return paciente


@router.post(
    "/paciente/registrar",
    status_code=status.HTTP_201_CREATED,
    summary="Registrar / actualizar datos del paciente (upsert)",
)
async def registrar_paciente(
    request: RequestRegistrarPaciente,
    user_id: CurrentUserId,
    registrar: RegistrarDep,
) -> dict:
    paciente_id = await registrar.ejecutar(user_id, request)
    return {"paciente_id": str(paciente_id)}
