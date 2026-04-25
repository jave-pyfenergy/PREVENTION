"""
PrevencionApp — Caso de Uso: PredecirInflamacion.
Orquesta la evaluación clínica completa: formulario → ML → persistencia → respuesta.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from uuid import uuid4

from starlette.concurrency import run_in_threadpool

from app.application.dto.dtos import RequestFormulario, ResponsePrediccion
from app.application.ports.hasher_port import HasherPort
from app.application.ports.ml_model_port import MLModelPort
from app.application.ports.repositorio_port import RepositorioPort
from app.application.ports.storage_port import StoragePort
from app.domain.entities.entities import (
    EvaluacionTemporal,
    Formulario,
    NivelRiesgo,
    ResultadoML,
    Sintomas,
)
from app.domain.services.evaluador_clinico import (
    DomainValidationError,
    EvaluadorClinico,
    ValidadorConsentimiento,
)

logger = logging.getLogger(__name__)


class PredecirInflamacion:
    """
    Caso de uso central del sistema.
    Implementa el flujo completo de evaluación clínica preventiva.
    """

    def __init__(
        self,
        ml_model: MLModelPort,
        repositorio: RepositorioPort,
        hasher: HasherPort,
        storage: StoragePort,
    ) -> None:
        self._ml = ml_model
        self._repo = repositorio
        self._hasher = hasher
        self._storage = storage
        self._evaluador = EvaluadorClinico()

    async def ejecutar(self, request: RequestFormulario) -> ResponsePrediccion:
        logger.info("Iniciando evaluación clínica", extra={"version": request.version_cuestionario})

        # 1. Construir entidad de dominio
        sintomas = Sintomas(
            dolor_articular=request.sintomas.dolor_articular,
            rigidez_matutina=request.sintomas.rigidez_matutina,
            duracion_rigidez_minutos=request.sintomas.duracion_rigidez_minutos,
            localizacion=request.sintomas.localizacion,
            inflamacion_visible=request.sintomas.inflamacion_visible,
            calor_local=request.sintomas.calor_local,
            limitacion_movimiento=request.sintomas.limitacion_movimiento,
        )
        formulario = Formulario(
            id=uuid4(),
            sintomas=sintomas,
            imagen_url=request.imagen_url,
            consentimiento=request.consentimiento,
            version_cuestionario=request.version_cuestionario,
            edad=request.edad,
            sexo=request.sexo,
            pais_id=request.pais_id,
        )

        # 2. Validar invariantes del dominio
        ValidadorConsentimiento.validar(formulario)
        if not formulario.validar():
            raise DomainValidationError("El formulario no cumple las invariantes del dominio")

        # 3. Preparar features para el modelo tabular
        features = self._extraer_features(formulario)

        # 4. Inferencia tabular (CPU-bound → threadpool)
        try:
            prob_tabular, conf_tabular = await self._ml.predecir(features)
        except Exception as e:
            logger.error("Error en inferencia tabular", exc_info=e)
            # Circuit breaker: valor neutro con baja confianza
            prob_tabular, conf_tabular = 0.5, 0.3

        # 5. Inferencia CNN (si hay imagen)
        prob_cnn = conf_cnn = gradcam_url = None
        if formulario.tiene_imagen():
            try:
                prob_cnn, conf_cnn, gradcam_url = await self._ml.analizar_imagen(
                    formulario.imagen_url  # type: ignore
                )
            except Exception as e:
                logger.warning("CNN no disponible, usando solo tabular", exc_info=e)

        # 6. Fusión de predicciones (ensemble)
        prob_final, conf_final = self._evaluador.fusionar_predicciones(
            prob_tabular, prob_cnn, conf_tabular, conf_cnn
        )
        nivel = self._evaluador.calcular_nivel(prob_final)

        # 7. Construir resultado
        resultado = ResultadoML(
            nivel_riesgo=nivel,
            probabilidad=prob_final,
            confianza=conf_final,
            gradcam_url=gradcam_url,
        )

        # 8. Persistir evaluación temporal (TTL 24h)
        session_id = str(uuid4())
        evaluacion = EvaluacionTemporal(
            id=uuid4(),
            session_id=session_id,
            formulario=formulario,
            resultado=resultado,
            fecha_expiracion=datetime.utcnow() + timedelta(hours=24),
            imagen_path_temp=self._extraer_path(formulario.imagen_url),
        )
        await self._repo.guardar_evaluacion_temporal(evaluacion)

        logger.info(
            "Evaluación completada",
            extra={
                "session_id": session_id,
                "nivel": nivel.value,
                "prob": prob_final,
                "confianza": conf_final,
            },
        )

        return ResponsePrediccion(
            evaluacion_id=evaluacion.id,
            session_id=session_id,
            nivel_inflamacion=nivel.value,
            probabilidad=prob_final,
            confianza=conf_final,
            es_confiable=resultado.es_confiable,
            gradcam_url=gradcam_url,
            recomendacion=resultado.recomendacion(),
            fecha=evaluacion.fecha_creacion,
        )

    @staticmethod
    def _extraer_features(formulario: Formulario) -> dict[str, float | int | bool]:
        s = formulario.sintomas
        if s is None:
            return {}
        return {
            "dolor_articular": int(s.dolor_articular),
            "rigidez_matutina": int(s.rigidez_matutina),
            "duracion_rigidez_minutos": s.duracion_rigidez_minutos,
            "inflamacion_visible": int(s.inflamacion_visible),
            "calor_local": int(s.calor_local),
            "limitacion_movimiento": int(s.limitacion_movimiento),
            "num_localizaciones": len(s.localizacion),
            "edad": formulario.edad or 0,
        }

    @staticmethod
    def _extraer_path(url: str | None) -> str | None:
        if url is None:
            return None
        # Extraer path del Signed URL de Supabase
        parts = url.split("/object/sign/")
        if len(parts) > 1:
            return parts[1].split("?")[0]
        return None
