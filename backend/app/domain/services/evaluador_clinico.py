"""
PrevencionApp — Servicios de Dominio.
Lógica de negocio que no pertenece a una única entidad.
"""
from __future__ import annotations

from app.domain.entities.entities import (
    Formulario,
    NivelRiesgo,
    ResultadoML,
    Sintomas,
)


class EvaluadorClinico:
    """
    Servicio de dominio — fusión de resultados tabulares y visuales.
    Implementa ensemble por media ponderada configurable.
    """

    # Pesos del ensemble: tabular (síntomas) vs visual (CNN)
    PESO_TABULAR = 0.60
    PESO_CNN = 0.40

    UMBRALES = {
        NivelRiesgo.BAJO: (0.0, 0.30),
        NivelRiesgo.MODERADO: (0.30, 0.60),
        NivelRiesgo.ALTO: (0.60, 0.85),
        NivelRiesgo.CRITICO: (0.85, 1.01),
    }

    @classmethod
    def calcular_nivel(cls, probabilidad: float) -> NivelRiesgo:
        for nivel, (low, high) in cls.UMBRALES.items():
            if low <= probabilidad < high:
                return nivel
        return NivelRiesgo.CRITICO

    @classmethod
    def fusionar_predicciones(
        cls,
        prob_tabular: float,
        prob_cnn: float | None,
        confianza_tabular: float,
        confianza_cnn: float | None,
    ) -> tuple[float, float]:
        """
        Retorna (probabilidad_final, confianza_final).
        Si no hay predicción CNN, usa solo el modelo tabular.
        """
        if prob_cnn is None or confianza_cnn is None:
            return prob_tabular, confianza_tabular

        prob_final = cls.PESO_TABULAR * prob_tabular + cls.PESO_CNN * prob_cnn
        conf_final = cls.PESO_TABULAR * confianza_tabular + cls.PESO_CNN * confianza_cnn
        return round(prob_final, 4), round(conf_final, 4)


class ValidadorConsentimiento:
    """Servicio de dominio — garantiza integridad del consentimiento informado."""

    @staticmethod
    def validar(formulario: Formulario) -> None:
        if not formulario.consentimiento:
            raise ConsentimientoRequeridoError(
                "Se requiere consentimiento informado explícito para procesar la evaluación"
            )

    @staticmethod
    def construir_texto_consentimiento(version: str = "1.0") -> str:
        return (
            f"[v{version}] Consiento que PrevencionApp procese mis datos de salud "
            "con fines de evaluación preventiva de inflamación sinovial. "
            "Entiendo que este análisis es orientativo y no reemplaza diagnóstico médico. "
            "Mis datos serán tratados conforme al GDPR, Ley 1581 y las políticas de privacidad."
        )


class ConsentimientoRequeridoError(Exception):
    """Error de dominio — operación bloqueada por falta de consentimiento."""
    pass


class DomainValidationError(Exception):
    """Error de dominio — entidad en estado inválido."""
    pass


class EvaluacionExpiradaError(Exception):
    """Error de dominio — la evaluación temporal ya expiró."""
    pass
