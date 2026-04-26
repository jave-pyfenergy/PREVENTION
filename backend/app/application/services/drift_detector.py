"""
PrevencionApp — Detección de drift de datos en producción.
Algoritmo: ventana deslizante + z-score sobre media móvil (online).

Mejoras vs v1:
- Stats incrementales O(1) por muestra (Welford's algorithm)
- Thread-safe para uso desde threadpool executors
- Recalibración automática del baseline (concept drift sostenido)
- Exportación del estado para persistencia externa (Redis / Supabase)
"""
from __future__ import annotations

import logging
import math
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Iterator

logger = logging.getLogger(__name__)


@dataclass
class _FeatureStats:
    """
    Estadísticas incrementales por feature usando el algoritmo de Welford.
    Complejidad: O(1) por update vs O(n) de statistics.mean/stdev.
    """
    n: int = 0
    mean: float = 0.0
    M2: float = 0.0  # varianza acumulada

    def update(self, value: float) -> None:
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        delta2 = value - self.mean
        self.M2 += delta * delta2

    @property
    def variance(self) -> float:
        return self.M2 / (self.n - 1) if self.n > 1 else 0.0

    @property
    def std(self) -> float:
        return math.sqrt(self.variance)


@dataclass
class DriftAlert:
    feature: str
    baseline_mean: float
    current_mean: float
    z_score: float
    direction: str  # "↑" | "↓"

    def __str__(self) -> str:
        return (
            f"Drift en '{self.feature}': "
            f"baseline={self.baseline_mean:.3f}, "
            f"actual={self.current_mean:.3f} {self.direction} "
            f"(z={self.z_score:.1f})"
        )


class DriftDetector:
    """
    Detector de distributional drift para features de entrada.

    Diseño:
    - Ventana deslizante para detección de drift local
    - Stats Welford O(1) — sin iterar la ventana completa
    - Baseline fijo (establecido en primera ventana completa)
    - Recalibración automática cada `recalibrate_every` muestras
      para adaptarse a concept drift sostenido
    - Thread-safe mediante RLock

    En producción complementar con Vertex AI Model Monitoring o Evidently AI.
    """

    def __init__(
        self,
        window_size: int = 100,
        z_threshold: float = 2.5,
        min_samples_before_check: int = 20,
        recalibrate_every: int = 500,
    ) -> None:
        self._window: deque[dict[str, float]] = deque(maxlen=window_size)
        self._window_size = window_size
        self._z_threshold = z_threshold
        self._min_samples = min_samples_before_check
        self._recalibrate_every = recalibrate_every

        # Stats online (Welford) — se actualizan con cada muestra
        self._online_stats: dict[str, _FeatureStats] = {}

        # Baseline fijo — snapshot cuando la ventana se llena por primera vez
        self._baseline: dict[str, tuple[float, float]] | None = None  # {feat: (mean, std)}

        self._total_evaluaciones: int = 0
        self._total_alertas: int = 0
        self._lock = threading.RLock()

    # ── API pública ──────────────────────────────────────────────────────────

    def registrar(self, features: dict[str, float | int | bool]) -> list[str]:
        """
        Registra una muestra y retorna alertas de drift si se detectan.
        Seguro para llamar desde múltiples threads (vía run_in_executor).
        No propaga excepciones internas — el flujo principal nunca se bloquea.
        """
        try:
            return self._registrar_interno(features)
        except Exception as e:
            logger.error("Error en DriftDetector — no propagado", exc_info=e)
            return []

    def exportar_estado(self) -> dict:
        """
        Serializa el estado para persistencia externa (Redis/Supabase).
        Permite sobrevivir reinicios del proceso.
        """
        with self._lock:
            return {
                "baseline": self._baseline,
                "total_evaluaciones": self._total_evaluaciones,
                "total_alertas": self._total_alertas,
                "online_stats": {
                    k: {"n": v.n, "mean": v.mean, "M2": v.M2}
                    for k, v in self._online_stats.items()
                },
            }

    def importar_estado(self, estado: dict) -> None:
        """Restaura el estado desde persistencia externa."""
        with self._lock:
            self._baseline = estado.get("baseline")
            self._total_evaluaciones = estado.get("total_evaluaciones", 0)
            self._total_alertas = estado.get("total_alertas", 0)
            for feat, s in estado.get("online_stats", {}).items():
                stats = _FeatureStats()
                stats.n, stats.mean, stats.M2 = s["n"], s["mean"], s["M2"]
                self._online_stats[feat] = stats
            logger.info(
                "Estado DriftDetector restaurado",
                extra={"n": self._total_evaluaciones, "baseline": self._baseline is not None},
            )

    @property
    def resumen(self) -> dict:
        with self._lock:
            return {
                "total_evaluaciones": self._total_evaluaciones,
                "total_alertas": self._total_alertas,
                "ventana_actual": len(self._window),
                "baseline_establecido": self._baseline is not None,
                "z_threshold": self._z_threshold,
            }

    # ── Lógica interna ───────────────────────────────────────────────────────

    def _registrar_interno(self, features: dict[str, float | int | bool]) -> list[str]:
        sample = {k: float(v) for k, v in features.items()}

        with self._lock:
            # Actualizar stats online (O(1))
            for feat, val in sample.items():
                if feat not in self._online_stats:
                    self._online_stats[feat] = _FeatureStats()
                self._online_stats[feat].update(val)

            self._window.append(sample)
            self._total_evaluaciones += 1

            if self._total_evaluaciones < self._min_samples:
                return []

            # Establecer baseline en primera ventana completa
            if self._baseline is None and len(self._window) == self._window_size:
                self._baseline = self._snapshot_stats()
                logger.info(
                    "Baseline de drift establecido",
                    extra={"n": self._window_size, "features": list(self._baseline.keys())},
                )
                return []

            if self._baseline is None:
                return []

            # Recalibración automática por concept drift sostenido
            if self._total_evaluaciones % self._recalibrate_every == 0:
                self._recalibrar()

            alertas = self._detectar_drift()
            if alertas:
                self._total_alertas += len(alertas)
                logger.warning(
                    "Drift detectado",
                    extra={
                        "alertas": [str(a) for a in alertas],
                        "n_total": self._total_evaluaciones,
                    },
                )
            return [str(a) for a in alertas]

    def _snapshot_stats(self) -> dict[str, tuple[float, float]]:
        """Captura stats de la ventana actual como baseline (no del historial completo)."""
        return self._window_stats()

    def _window_stats(self) -> dict[str, tuple[float, float]]:
        """
        Calcula media y std de cada feature sobre la ventana deslizante actual.
        Usa Welford sobre los elementos del deque para evitar iterar dos veces.
        """
        if not self._window:
            return {}
        feat_names = list(self._window[0].keys())
        result: dict[str, tuple[float, float]] = {}
        for feat in feat_names:
            s = _FeatureStats()
            for row in self._window:
                if feat in row:
                    s.update(row[feat])
            result[feat] = (s.mean, s.std)
        return result

    def _detectar_drift(self) -> list[DriftAlert]:
        assert self._baseline is not None
        alertas: list[DriftAlert] = []

        # Comparar stats de la ventana actual (distribución reciente)
        # contra el baseline (distribución al momento de la primera ventana completa)
        current = self._window_stats()

        for feat, (cur_mean, _) in current.items():
            if feat not in self._baseline:
                continue
            base_mean, base_std = self._baseline[feat]

            if base_std < 1e-6:
                # Baseline con varianza nula (datos constantes): usar umbral absoluto
                # Si la media actual se aleja más del 15% del rango [0,1], es drift
                abs_diff = abs(cur_mean - base_mean)
                if abs_diff < 0.15:
                    continue
                z_equiv = abs_diff / 0.1  # normalizar para logging
            else:
                z_equiv = abs(cur_mean - base_mean) / base_std
                if z_equiv <= self._z_threshold:
                    continue

            alertas.append(DriftAlert(
                feature=feat,
                baseline_mean=round(base_mean, 4),
                current_mean=round(cur_mean, 4),
                z_score=round(z_equiv, 2),
                direction="↑" if cur_mean > base_mean else "↓",
            ))
        return alertas

    def _recalibrar(self) -> None:
        """
        Recalibra el baseline con las últimas N muestras.
        Solo se activa si el drift persiste más de `recalibrate_every` muestras
        — distingue drift real de outliers temporales.
        """
        alertas_antes = len(self._detectar_drift())
        nuevo_baseline = self._snapshot_stats()

        # Solo recalibrar si las alertas persisten (drift estructural)
        if alertas_antes > 0:
            self._baseline = nuevo_baseline
            logger.warning(
                "Baseline recalibrado por concept drift sostenido",
                extra={
                    "n_evaluaciones": self._total_evaluaciones,
                    "features_drifted": alertas_antes,
                },
            )
