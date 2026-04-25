"""
PrevencionApp — Casos de Uso secundarios.
VincularEvaluacion, ObtenerHistorial, RegistrarPaciente.
"""
from __future__ import annotations

import logging
from uuid import UUID

from app.application.dto.dtos import (
    HistorialItem,
    PacienteDTO,
    RequestRegistrarPaciente,
    RequestVincularEvaluacion,
    ResponseHistorial,
)
from app.application.ports.hasher_port import HasherPort
from app.application.ports.repositorio_port import RepositorioPort
from app.application.ports.storage_port import StoragePort
from app.domain.services.evaluador_clinico import DomainValidationError

logger = logging.getLogger(__name__)


class VincularEvaluacion:
    """
    Vincula una evaluación anónima al usuario autenticado.
    Mueve la imagen de temp_images a permanent_images/{user_id}/.
    """

    def __init__(self, repositorio: RepositorioPort, storage: StoragePort) -> None:
        self._repo = repositorio
        self._storage = storage

    async def ejecutar(self, request: RequestVincularEvaluacion) -> None:
        evaluacion = await self._repo.obtener_evaluacion_por_session(
            str(request.evaluacion_id)
        )
        if evaluacion is None:
            raise DomainValidationError(f"Evaluación {request.evaluacion_id} no encontrada")

        if evaluacion.esta_expirada():
            raise DomainValidationError("La evaluación temporal ha expirado")

        if evaluacion.esta_vinculada():
            raise DomainValidationError("La evaluación ya está vinculada a un usuario")

        # Mover imagen si existe
        if evaluacion.imagen_path_temp:
            try:
                await self._storage.mover_imagen_a_permanente(
                    evaluacion.imagen_path_temp, request.user_id
                )
            except Exception as e:
                logger.warning("No se pudo mover la imagen", exc_info=e)

        # Vincular en base de datos
        await self._repo.vincular_evaluacion_a_usuario(
            request.evaluacion_id, request.user_id
        )
        logger.info(
            "Evaluación vinculada",
            extra={"evaluacion_id": str(request.evaluacion_id), "user_id": str(request.user_id)},
        )


class ObtenerHistorial:
    """Retorna el historial paginado de evaluaciones del usuario autenticado."""

    def __init__(self, repositorio: RepositorioPort) -> None:
        self._repo = repositorio

    async def ejecutar(
        self, user_id: UUID, page: int = 1, page_size: int = 20
    ) -> ResponseHistorial:
        page = max(1, page)
        page_size = min(100, max(1, page_size))

        items, total = await self._repo.obtener_historial(user_id, page, page_size)
        has_next = (page * page_size) < total

        return ResponseHistorial(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=has_next,
        )


class RegistrarPaciente:
    """
    Upsert de datos demográficos del paciente.
    Hashea PII antes de persistir — Privacy by Design.
    """

    def __init__(self, repositorio: RepositorioPort, hasher: HasherPort) -> None:
        self._repo = repositorio
        self._hasher = hasher

    async def ejecutar(
        self, user_id: UUID, request: RequestRegistrarPaciente
    ) -> UUID:
        if not request.primer_nombre or not request.primer_apellido:
            raise DomainValidationError("Nombre y apellido son obligatorios")

        # Hashear PII antes de persistir
        id_hash = await self._hasher.hashear(request.identificacion)
        tel_hash = None
        if request.telefono:
            tel_hash = await self._hasher.hashear(request.telefono)

        paciente_id = await self._repo.registrar_paciente_full(
            user_id=user_id,
            request=request,
            identificacion_hash=id_hash,
            telefono_hash=tel_hash,
        )
        logger.info("Paciente registrado", extra={"paciente_id": str(paciente_id)})
        return paciente_id
