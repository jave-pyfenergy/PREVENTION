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
        """Retorna (probabilidad_final, confianza_final)."""
        if prob_cnn is None or confianza_cnn is None:
            return prob_tabular, confianza_tabular

        prob_final = cls.PESO_TABULAR * prob_tabular + cls.PESO_CNN * prob_cnn
        conf_final = cls.PESO_TABULAR * confianza_tabular + cls.PESO_CNN * confianza_cnn
        return round(prob_final, 4), round(conf_final, 4)


class ReglasClinicas:
    """
    Motor de reglas clínicas — ajusta la predicción ML con conocimiento experto.
    Implementa patrones clínicos de artritis reumatoide e inflamación sinovial.
    """

    @staticmethod
    def aplicar(
        formulario: Formulario, prob_ml: float
    ) -> tuple[float, list[str]]:
        """
        Aplica reglas clínicas sobre la probabilidad base del ML.
        Retorna (prob_ajustada, reglas_aplicadas).
        """
        s = formulario.sintomas
        if s is None:
            return prob_ml, []

        ajuste = 0.0
        reglas: list[str] = []

        # Regla 1: Tríada clásica de sinovitis activa
        if s.inflamacion_visible and s.calor_local and s.limitacion_movimiento:
            ajuste += 0.08
            reglas.append("Tríada clásica (inflamación + calor + limitación): alta especificidad de sinovitis")

        # Regla 2: Rigidez matutina inflamatoria (≥60 min es criterio ACR/EULAR)
        if s.rigidez_matutina and s.duracion_rigidez_minutos >= 60:
            ajuste += 0.06
            reglas.append(
                f"Rigidez matutina inflamatoria ≥60 min ({s.duracion_rigidez_minutos} min) "
                "— criterio ACR/EULAR para artritis inflamatoria"
            )

        # Regla 3: Patrón poliarticular (≥4 articulaciones)
        if len(s.localizacion) >= 4:
            ajuste += 0.05
            reglas.append(
                f"Afectación poliarticular ({len(s.localizacion)} articulaciones) "
                "— patrón sugestivo de artritis reumatoide"
            )

        # Regla 4: Todos los síntomas cardinales presentes
        cardinales = [s.dolor_articular, s.rigidez_matutina, s.inflamacion_visible,
                      s.calor_local, s.limitacion_movimiento]
        if all(cardinales):
            ajuste += 0.05
            reglas.append("Todos los síntomas cardinales presentes — cuadro clínico completo")

        # Regla 5: Franja etaria de mayor prevalencia de AR (30-60 años)
        if formulario.edad and 30 <= formulario.edad <= 60 and s.dolor_articular and s.rigidez_matutina:
            ajuste += 0.03
            reglas.append(
                f"Edad en franja de mayor prevalencia de AR ({formulario.edad} años) "
                "con síntomas articulares"
            )

        # Regla 6: Síntomas bilaterales (manos o rodillas bilaterales) — patrón simétrico
        pares = [
            ("mano_derecha", "mano_izquierda"),
            ("rodilla_derecha", "rodilla_izquierda"),
            ("muneca_derecha", "muneca_izquierda"),
            ("hombro_derecho", "hombro_izquierdo"),
        ]
        pares_simetricos = sum(
            1 for a, b in pares if a in s.localizacion and b in s.localizacion
        )
        if pares_simetricos >= 2:
            ajuste += 0.04
            reglas.append(
                f"Distribución simétrica ({pares_simetricos} pares afectados) "
                "— característico de artritis reumatoide"
            )

        prob_final = min(round(prob_ml + ajuste, 4), 1.0)
        return prob_final, reglas


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
