"""
PrevencionApp — Adaptador Supabase (PostgreSQL).
Implementa el RepositorioPort usando el SDK oficial de Supabase.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from supabase import create_client, Client

from app.application.dto.dtos import (
    HistorialItem,
    PacienteDTO,
    RequestRegistrarPaciente,
)
from app.application.ports.ports import RepositorioPort
from app.domain.entities.entities import (
    EvaluacionTemporal,
    Formulario,
    NivelRiesgo,
    ResultadoML,
    Sintomas,
)

logger = logging.getLogger(__name__)


class SupabaseAdapter(RepositorioPort):
    def __init__(self, url: str, service_key: str) -> None:
        # service_role bypass RLS para operaciones del backend
        self._client: Client = create_client(url, service_key)

    async def guardar_evaluacion_temporal(
        self, evaluacion: EvaluacionTemporal
    ) -> EvaluacionTemporal:
        formulario = evaluacion.formulario
        resultado = evaluacion.resultado

        payload: dict[str, Any] = {
            "id": str(evaluacion.id),
            "session_id": evaluacion.session_id,
            "consentimiento": formulario.consentimiento if formulario else False,
            "version_cuestionario": formulario.version_cuestionario if formulario else "1.0",
            "nivel_inflamacion": resultado.nivel_riesgo.value if resultado else None,
            "probabilidad": resultado.probabilidad if resultado else None,
            "confianza": resultado.confianza if resultado else None,
            "gradcam_url": resultado.gradcam_url if resultado else None,
            "imagen_path_temp": evaluacion.imagen_path_temp,
            "fecha_expiracion": evaluacion.fecha_expiracion.isoformat()
            if evaluacion.fecha_expiracion
            else None,
        }

        # Serializar síntomas en JSONB
        if formulario and formulario.sintomas:
            s = formulario.sintomas
            payload["respuestas_completas"] = {
                "dolor_articular": s.dolor_articular,
                "rigidez_matutina": s.rigidez_matutina,
                "duracion_rigidez_minutos": s.duracion_rigidez_minutos,
                "localizacion": s.localizacion,
                "inflamacion_visible": s.inflamacion_visible,
                "calor_local": s.calor_local,
                "limitacion_movimiento": s.limitacion_movimiento,
            }
            # Columnas desnormalizadas para queries rápidos
            payload["p12a"] = s.dolor_articular
            payload["p13a"] = s.rigidez_matutina
            payload["p14"] = s.duracion_rigidez_minutos
            payload["p15"] = s.inflamacion_visible

        try:
            self._client.table("evaluaciones").insert(payload).execute()
            logger.debug("Evaluación temporal guardada", extra={"id": str(evaluacion.id)})
        except Exception as e:
            logger.error("Error guardando evaluación", exc_info=e)
            raise

        return evaluacion

    async def obtener_evaluacion_por_session(
        self, session_id: str
    ) -> EvaluacionTemporal | None:
        try:
            result = (
                self._client.table("evaluaciones")
                .select("*")
                .eq("session_id", session_id)
                .single()
                .execute()
            )
            if not result.data:
                return None
            return self._mapear_evaluacion(result.data)
        except Exception as e:
            logger.error("Error obteniendo evaluación por session", exc_info=e)
            return None

    async def vincular_evaluacion_a_usuario(
        self, evaluacion_id: UUID, user_id: UUID
    ) -> None:
        self._client.table("evaluaciones").update(
            {"user_id": str(user_id), "paciente_activo": True}
        ).eq("id", str(evaluacion_id)).execute()

    async def obtener_historial(
        self, user_id: UUID, page: int, page_size: int
    ) -> tuple[list[HistorialItem], int]:
        offset = (page - 1) * page_size

        result = (
            self._client.table("evaluaciones")
            .select("id, fecha_creacion, nivel_inflamacion, probabilidad, imagen_path_temp")
            .eq("user_id", str(user_id))
            .order("fecha_creacion", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )

        count_result = (
            self._client.table("evaluaciones")
            .select("id", count="exact")
            .eq("user_id", str(user_id))
            .execute()
        )

        items = [
            HistorialItem(
                evaluacion_id=row["id"],
                fecha=datetime.fromisoformat(row["fecha_creacion"]),
                nivel_inflamacion=row.get("nivel_inflamacion", "desconocido"),
                probabilidad=row.get("probabilidad", 0.0),
                tiene_imagen=bool(row.get("imagen_path_temp")),
            )
            for row in (result.data or [])
        ]

        total = count_result.count or 0
        return items, total

    async def registrar_paciente_full(
        self,
        user_id: UUID,
        request: RequestRegistrarPaciente,
        identificacion_hash: str,
        telefono_hash: str | None,
    ) -> UUID:
        """Llama a la RPC atómica de PostgreSQL."""
        result = self._client.rpc(
            "registrar_paciente_full",
            {
                "p_user_id": str(user_id),
                "p_primer_nombre": request.primer_nombre,
                "p_primer_apellido": request.primer_apellido,
                "p_segundo_nombre": request.segundo_nombre,
                "p_segundo_apellido": request.segundo_apellido,
                "p_identificacion_hash": identificacion_hash,
                "p_tipo_identificacion_id": request.tipo_identificacion_id,
                "p_telefono_hash": telefono_hash,
                "p_fecha_nacimiento": request.fecha_nacimiento.isoformat()
                if request.fecha_nacimiento
                else None,
                "p_sexo_id": request.sexo_id,
                "p_pais_id": request.pais_id,
                "p_ciudad_id": request.ciudad_id,
            },
        ).execute()

        return UUID(result.data)

    async def obtener_paciente(self, user_id: UUID) -> PacienteDTO | None:
        result = (
            self._client.table("pacientes")
            .select("id, user_id, primer_nombre, primer_apellido, fecha_nacimiento, pais_id, fecha_creacion")
            .eq("user_id", str(user_id))
            .eq("activo", True)
            .single()
            .execute()
        )
        if not result.data:
            return None
        d = result.data
        return PacienteDTO(
            id=UUID(d["id"]),
            user_id=UUID(d["user_id"]),
            primer_nombre=d["primer_nombre"],
            primer_apellido=d["primer_apellido"],
            fecha_nacimiento=datetime.fromisoformat(d["fecha_nacimiento"])
            if d.get("fecha_nacimiento")
            else None,
            pais_id=d.get("pais_id"),
            fecha_creacion=datetime.fromisoformat(d["fecha_creacion"]),
        )

    @staticmethod
    def _mapear_evaluacion(data: dict) -> EvaluacionTemporal:
        from uuid import UUID as _UUID
        evaluacion = EvaluacionTemporal(
            id=_UUID(data["id"]),
            session_id=data["session_id"],
            user_id=_UUID(data["user_id"]) if data.get("user_id") else None,
            imagen_path_temp=data.get("imagen_path_temp"),
        )
        if data.get("fecha_expiracion"):
            evaluacion.fecha_expiracion = datetime.fromisoformat(data["fecha_expiracion"])
        return evaluacion
