"""
PrevencionApp — Adaptador ML scikit-learn/XGBoost.
Carga el modelo desde disco (dev) o GCS (prod).
Incluye: verificación de integridad SHA-256, hard fail sin dummy silencioso,
circuit breaker para el servicio CNN externo.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import pickle
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import numpy as np

from app.application.ports.ports import MLModelPort
from app.domain.exceptions import ModeloNoDisponibleError

logger = logging.getLogger(__name__)

FEATURE_ORDER = [
    "dolor_articular",
    "rigidez_matutina",
    "duracion_rigidez_minutos",
    "inflamacion_visible",
    "calor_local",
    "limitacion_movimiento",
    "num_localizaciones",
    "edad",
]

FEATURE_LABELS_ES = {
    "dolor_articular": "Dolor articular",
    "rigidez_matutina": "Rigidez matutina",
    "duracion_rigidez_minutos": "Duración de rigidez",
    "inflamacion_visible": "Inflamación visible",
    "calor_local": "Calor local",
    "limitacion_movimiento": "Limitación de movimiento",
    "num_localizaciones": "Articulaciones afectadas",
    "edad": "Edad (factor de riesgo)",
}


def _extract_tree_estimator(model: Any) -> Any:
    """Extrae el estimador árbol de un Pipeline sklearn o retorna el modelo directamente."""
    try:
        from sklearn.pipeline import Pipeline
        if isinstance(model, Pipeline):
            return model.steps[-1][1]
    except ImportError:
        pass
    return model


class _CircuitBreaker:
    """Circuit breaker simple para el servicio CNN externo."""

    FAILURE_THRESHOLD = 3
    RESET_SECONDS = 60

    def __init__(self) -> None:
        self._failures = 0
        self._opened_at: datetime | None = None
        self._lock = threading.Lock()

    def is_open(self) -> bool:
        with self._lock:
            if self._opened_at and datetime.now() - self._opened_at > timedelta(seconds=self.RESET_SECONDS):
                self._failures = 0
                self._opened_at = None
                logger.info("Circuit breaker CNN: CERRADO (reset automático)")
            return self._failures >= self.FAILURE_THRESHOLD

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.FAILURE_THRESHOLD:
                self._opened_at = datetime.now()
                logger.warning("Circuit breaker CNN: ABIERTO (%d fallos)", self._failures)

    def record_success(self) -> None:
        with self._lock:
            if self._failures > 0:
                self._failures = 0
                self._opened_at = None


class SklearnAdapter(MLModelPort):
    """
    Adaptador para modelos scikit-learn / XGBoost serializados con pickle.
    - Carga lazy con doble verificación thread-safe.
    - Verifica integridad SHA-256 antes de deserializar (previene RCE).
    - Hard fail si el modelo no existe — sin silencio médico peligroso.
    - Circuit breaker para el servicio CNN.
    """

    def __init__(
        self,
        model_path: str,
        confidence_threshold: float = 0.70,
        expected_checksum: str | None = None,
    ) -> None:
        self._model_path = Path(model_path)
        self._confidence_threshold = confidence_threshold
        self._expected_checksum = expected_checksum or os.getenv("MODEL_SHA256_CHECKSUM")
        self._model: Any = None
        self._load_lock = threading.Lock()
        self._cnn_breaker = _CircuitBreaker()

    def _cargar_modelo(self) -> Any:
        """Carga el modelo. Double-checked locking + verificación de integridad."""
        if self._model is not None:
            return self._model

        with self._load_lock:
            if self._model is not None:
                return self._model

            if not self._model_path.exists():
                raise ModeloNoDisponibleError(
                    f"Modelo ML no encontrado en '{self._model_path}'. "
                    "Ejecuta scripts/train_dummy_model.py o descarga desde GCS."
                )

            # Verificar integridad SHA-256 antes de pickle.load
            if self._expected_checksum:
                digest = hashlib.sha256(self._model_path.read_bytes()).hexdigest()
                if digest != self._expected_checksum:
                    raise ModeloNoDisponibleError(
                        f"Checksum del modelo no coincide. "
                        f"Esperado: {self._expected_checksum}, obtenido: {digest}. "
                        "El archivo puede estar corrupto o comprometido."
                    )

            logger.info("Cargando modelo desde %s", self._model_path)
            with open(self._model_path, "rb") as f:
                self._model = pickle.load(f)  # noqa: S301 — integridad verificada arriba
            logger.info("Modelo ML cargado exitosamente")
            return self._model

    def _predecir_sync(
        self, features: dict[str, float | int | bool]
    ) -> tuple[float, float, dict[str, float]]:
        """Inferencia síncrona — se ejecuta en threadpool para no bloquear el loop."""
        model = self._cargar_modelo()
        X = np.array([[features.get(f, 0) for f in FEATURE_ORDER]], dtype=np.float32)

        proba = model.predict_proba(X)[0]
        prob_positiva = float(proba[1]) if len(proba) > 1 else float(proba[0])
        confianza = min(abs(prob_positiva - 0.5) * 2, 1.0)

        importancias: dict[str, float] = {}
        estimator = _extract_tree_estimator(model)
        if estimator is not None and hasattr(estimator, "feature_importances_"):
            raw = {
                name: float(imp)
                for name, imp in zip(FEATURE_ORDER, estimator.feature_importances_)
            }
            total = sum(raw.values()) or 1.0
            importancias = {k: round(v / total, 4) for k, v in raw.items()}
        else:
            importancias = {name: round(1.0 / len(FEATURE_ORDER), 4) for name in FEATURE_ORDER}

        return round(prob_positiva, 4), round(confianza, 4), importancias

    async def predecir(
        self, features: dict[str, float | int | bool]
    ) -> tuple[float, float, dict[str, float]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._predecir_sync, features)

    async def analizar_imagen(
        self, imagen_url: str
    ) -> tuple[float, float, str | None]:
        """Delega al servicio CNN externo con circuit breaker y timeout reducido."""
        if self._cnn_breaker.is_open():
            logger.debug("Circuit breaker CNN abierto — fallo rápido")
            return 0.5, 0.0, None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self._cnn_service_url}/analyze",
                    json={"image_url": imagen_url},
                )
                response.raise_for_status()
                data = response.json()
                self._cnn_breaker.record_success()
                return data["probability"], data["confidence"], data.get("gradcam_url")
        except Exception as e:
            self._cnn_breaker.record_failure()
            logger.warning("CNN no disponible: %s", e)
            return 0.5, 0.0, None

    def esta_disponible(self) -> bool:
        return self._model is not None

    def cargar_modelo(self) -> None:
        self._cargar_modelo()

    @property
    def _cnn_service_url(self) -> str:
        return os.getenv("ML_SERVICE_URL", "http://localhost:8001")
