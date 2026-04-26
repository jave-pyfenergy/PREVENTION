"""
PrevencionApp — Caso de Uso: PredecirInflamacion.
Orquesta la evaluación clínica completa: formulario → ML → reglas clínicas → persistencia → respuesta.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import structlog

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
from app.application.services.drift_detector import DriftDetector
from app.domain.services.evaluador_clinico import (
    DomainValidationError,
    EvaluadorClinico,
    ReglasClinicas,
    ValidadorConsentimiento,
)

logger = structlog.get_logger(__name__)


class PredecirInflamacion:
    """
    Caso de uso central del sistema.
    Pipeline: síntomas → ML tabular → CNN (opcional) → reglas clínicas → respuesta XAI.
    """

    def __init__(
        self,
        ml_model: MLModelPort,
        repositorio: RepositorioPort,
        hasher: HasherPort,
        storage: StoragePort,
        drift_detector: DriftDetector | None = None,
    ) -> None:
        self._ml = ml_model
        self._repo = repositorio
        self._hasher = hasher
        self._storage = storage
        self._evaluador = EvaluadorClinico()
        self._drift_detector = drift_detector

    async def ejecutar(self, request: RequestFormulario) -> ResponsePrediccion:
        t0 = time.perf_counter()
        logger.info("evaluacion_iniciada", version=request.version_cuestionario)

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

        # Registrar en drift detector (no bloqueante)
        if self._drift_detector is not None:
            self._drift_detector.registrar(features)

        # 4. Inferencia tabular — retorna (probabilidad, confianza, importancias)
        try:
            t_ml = time.perf_counter()
            prob_tabular, conf_tabular, features_importantes = await self._ml.predecir(features)
            logger.debug("inferencia_tabular_ok", ms=round((time.perf_counter() - t_ml) * 1000, 1))
        except Exception as e:
            logger.error("inferencia_tabular_fallida", error=str(e))
            prob_tabular, conf_tabular, features_importantes = 0.5, 0.3, {}

        # 5. Inferencia CNN (si hay imagen)
        prob_cnn = conf_cnn = gradcam_url = None
        if formulario.tiene_imagen():
            try:
                prob_cnn, conf_cnn, gradcam_url = await self._ml.analizar_imagen(
                    formulario.imagen_url  # type: ignore
                )
            except Exception as e:
                logger.warning("cnn_no_disponible", error=str(e))

        # 6. Fusión de predicciones (ensemble)
        prob_ml, conf_final = self._evaluador.fusionar_predicciones(
            prob_tabular, prob_cnn, conf_tabular, conf_cnn
        )

        # 7. Motor de reglas clínicas — ajuste experto sobre predicción ML
        prob_final, reglas_clinicas = ReglasClinicas.aplicar(formulario, prob_ml)
        if reglas_clinicas:
            logger.info("reglas_clinicas_aplicadas", n=len(reglas_clinicas), ajuste=round(prob_final - prob_ml, 4))

        nivel = self._evaluador.calcular_nivel(prob_final)

        # 8. Construir resultado con XAI
        resultado = ResultadoML(
            nivel_riesgo=nivel,
            probabilidad=prob_final,
            confianza=conf_final,
            gradcam_url=gradcam_url,
            features_importantes=features_importantes,
        )

        # 9. Persistir evaluación temporal (TTL 24h)
        session_id = str(uuid4())
        evaluacion = EvaluacionTemporal(
            id=uuid4(),
            session_id=session_id,
            formulario=formulario,
            resultado=resultado,
            fecha_expiracion=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24),
            imagen_path_temp=self._extraer_path(formulario.imagen_url),
        )
        try:
            await self._repo.guardar_evaluacion_temporal(evaluacion)
        except Exception as exc:
            logger.warning("persistencia_no_disponible", error=str(exc))

        logger.info(
            "evaluacion_completada",
            session_id=session_id,
            nivel=nivel.value,
            prob_ml=round(prob_ml, 4),
            prob_final=round(prob_final, 4),
            confianza=round(conf_final, 4),
            reglas=len(reglas_clinicas),
            total_ms=round((time.perf_counter() - t0) * 1000, 1),
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
            features_importantes=features_importantes,
            reglas_clinicas=reglas_clinicas,
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
        parts = url.split("/object/sign/")
        if len(parts) > 1:
            return parts[1].split("?")[0]
        return None
