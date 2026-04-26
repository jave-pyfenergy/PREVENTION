"""
PrevencionApp — Adaptador Supabase (PostgreSQL).
Todas las llamadas al SDK síncrono se ejecutan en run_in_executor para
no bloquear el event loop de asyncio.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from functools import partial
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
from app.domain.exceptions import (
    EvaluacionYaVinculadaError,
    EvaluacionNoEncontradaError,
)

logger = logging.getLogger(__name__)

# Columnas a seleccionar en consultas de evaluación (nunca SELECT *)
_EVAL_COLS = (
    "id,session_id,user_id,imagen_path_temp,fecha_creacion,fecha_expiracion,"
    "nivel_inflamacion,probabilidad,confianza,gradcam_url,features_importantes,"
    "respuestas_completas,version_cuestionario,consentimiento"
)
_HISTORIAL_COLS = (
    "id,session_id,fecha_creacion,nivel_inflamacion,probabilidad,imagen_path_temp"
)


class SupabaseAdapter(RepositorioPort):
    def __init__(self, url: str, service_key: str) -> None:
        self._client: Client = create_client(url, service_key)

    # ── Helper: ejecuta función síncrona en el threadpool ─────────────────────

    async def _run(self, fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    # ── Evaluaciones ──────────────────────────────────────────────────────────

    async def guardar_evaluacion_temporal(
        self, evaluacion: EvaluacionTemporal
    ) -> EvaluacionTemporal:
        payload = self._build_payload(evaluacion)
        await self._run(
            lambda: self._client.table("evaluaciones").insert(payload).execute()
        )
        logger.debug("Evaluación temporal guardada: %s", evaluacion.id)
        return evaluacion

    async def obtener_evaluacion_por_session(
        self, session_id: str
    ) -> EvaluacionTemporal | None:
        try:
            result = await self._run(
                lambda: self._client.table("evaluaciones")
                .select(_EVAL_COLS)
                .eq("session_id", session_id)
                .single()
                .execute()
            )
            if not result.data:
                return None
            return self._mapear_evaluacion(result.data)
        except Exception as e:
            logger.error("Error obteniendo evaluación por session: %s", e)
            return None

    async def obtener_evaluacion_por_id(
        self, evaluacion_id: UUID
    ) -> EvaluacionTemporal | None:
        try:
            result = await self._run(
                lambda: self._client.table("evaluaciones")
                .select(_EVAL_COLS)
                .eq("id", str(evaluacion_id))
                .single()
                .execute()
            )
            if not result.data:
                return None
            return self._mapear_evaluacion(result.data)
        except Exception as e:
            logger.error("Error obteniendo evaluación por id: %s", e)
            return None

    async def vincular_evaluacion_a_usuario(
        self, evaluacion_id: UUID, user_id: UUID
    ) -> None:
        """UPDATE atómico: solo vincula si todavía es anónima (user_id IS NULL).
        Elimina la race condition de doble-vincular."""
        result = await self._run(
            lambda: self._client.table("evaluaciones")
            .update({"user_id": str(user_id), "paciente_activo": True})
            .eq("id", str(evaluacion_id))
            .is_("user_id", "null")
            .execute()
        )
        if not result.data:
            raise EvaluacionYaVinculadaError(
                f"La evaluación {evaluacion_id} ya está vinculada o no existe"
            )

    async def obtener_historial(
        self, user_id: UUID, page: int, page_size: int
    ) -> tuple[list[HistorialItem], int]:
        offset = (page - 1) * page_size
        # Una sola query con count exacto — elimina el N+1 anterior
        result = await self._run(
            lambda: self._client.table("evaluaciones")
            .select(_HISTORIAL_COLS, count="exact")
            .eq("user_id", str(user_id))
            .order("fecha_creacion", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        items = [self._to_historial_item(r) for r in (result.data or [])]
        return items, result.count or 0

    async def registrar_paciente_full(
        self,
        user_id: UUID,
        request: RequestRegistrarPaciente,
        identificacion_hash: str,
        telefono_hash: str | None,
    ) -> UUID:
        result = await self._run(
            lambda: self._client.rpc(
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
        )
        return UUID(result.data)

    async def obtener_paciente(self, user_id: UUID) -> PacienteDTO | None:
        result = await self._run(
            lambda: self._client.table("pacientes")
            .select(
                "id,user_id,primer_nombre,primer_apellido,"
                "fecha_nacimiento,pais_id,fecha_creacion"
            )
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

    # ── Helpers privados ──────────────────────────────────────────────────────

    @staticmethod
    def _build_payload(evaluacion: EvaluacionTemporal) -> dict[str, Any]:
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
            "features_importantes": resultado.features_importantes if resultado else None,
            "imagen_path_temp": evaluacion.imagen_path_temp,
            "fecha_expiracion": evaluacion.fecha_expiracion.isoformat()
            if evaluacion.fecha_expiracion
            else None,
        }
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
            # Columnas desnormalizadas para queries rápidos en dashboard
            payload["p12a"] = s.dolor_articular
            payload["p13a"] = s.rigidez_matutina
            payload["p14"] = s.duracion_rigidez_minutos
            payload["p15"] = s.inflamacion_visible
        return payload

    @staticmethod
    def _mapear_evaluacion(data: dict) -> EvaluacionTemporal:
        evaluacion = EvaluacionTemporal(
            id=UUID(data["id"]),
            session_id=data["session_id"],
            user_id=UUID(data["user_id"]) if data.get("user_id") else None,
            imagen_path_temp=data.get("imagen_path_temp"),
        )
        if data.get("fecha_creacion"):
            evaluacion.fecha_creacion = datetime.fromisoformat(data["fecha_creacion"])
        if data.get("fecha_expiracion"):
            evaluacion.fecha_expiracion = datetime.fromisoformat(data["fecha_expiracion"])

        # Reconstruir Sintomas desde JSONB
        respuestas = data.get("respuestas_completas") or {}
        if respuestas:
            try:
                sintomas = Sintomas(
                    dolor_articular=respuestas.get("dolor_articular", False),
                    rigidez_matutina=respuestas.get("rigidez_matutina", False),
                    duracion_rigidez_minutos=respuestas.get("duracion_rigidez_minutos", 0),
                    localizacion=respuestas.get("localizacion", []),
                    inflamacion_visible=respuestas.get("inflamacion_visible", False),
                    calor_local=respuestas.get("calor_local", False),
                    limitacion_movimiento=respuestas.get("limitacion_movimiento", False),
                )
                evaluacion.formulario = Formulario(
                    consentimiento=data.get("consentimiento", True),
                    version_cuestionario=data.get("version_cuestionario", "1.0"),
                    sintomas=sintomas,
                )
            except Exception as e:
                logger.warning("No se pudo reconstruir Formulario desde DB: %s", e)

        # Reconstruir ResultadoML
        nivel_raw = data.get("nivel_inflamacion")
        probabilidad = data.get("probabilidad")
        confianza = data.get("confianza")
        if nivel_raw is not None and probabilidad is not None and confianza is not None:
            try:
                evaluacion.resultado = ResultadoML(
                    nivel_riesgo=NivelRiesgo(nivel_raw),
                    probabilidad=float(probabilidad),
                    confianza=float(confianza),
                    gradcam_url=data.get("gradcam_url"),
                    features_importantes=data.get("features_importantes") or {},
                )
            except (ValueError, KeyError) as e:
                logger.warning("No se pudo reconstruir ResultadoML: %s", e)

        return evaluacion

    @staticmethod
    def _to_historial_item(row: dict) -> HistorialItem:
        return HistorialItem(
            evaluacion_id=row["id"],
            session_id=row["session_id"],
            fecha=datetime.fromisoformat(row["fecha_creacion"]),
            nivel_inflamacion=row.get("nivel_inflamacion", "desconocido"),
            probabilidad=row.get("probabilidad", 0.0),
            tiene_imagen=bool(row.get("imagen_path_temp")),
        )
