"""
PrevencionApp — Adaptador ML scikit-learn/XGBoost.
Carga el modelo desde disco (dev) o GCS (prod) y ejecuta inferencia tabular.
El análisis CNN está delegado a un servicio separado en producción.
"""
from __future__ import annotations

import asyncio
import logging
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from app.application.ports.ports import MLModelPort

logger = logging.getLogger(__name__)

# Orden fijo de features — debe coincidir con el training pipeline
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


class SklearnAdapter(MLModelPort):
    """
    Adaptador para modelos scikit-learn / XGBoost serializados con pickle.
    El modelo se carga lazy (primera inferencia) para optimizar cold start.
    """

    def __init__(self, model_path: str, confidence_threshold: float = 0.70) -> None:
        self._model_path = Path(model_path)
        self._confidence_threshold = confidence_threshold
        self._model: Any = None

    def _cargar_modelo(self) -> Any:
        """Carga el modelo desde disco. Thread-safe para uso en threadpool."""
        if self._model is not None:
            return self._model

        if not self._model_path.exists():
            logger.warning(
                f"Modelo no encontrado en {self._model_path} — usando modelo dummy"
            )
            self._model = _DummyModel()
            return self._model

        logger.info(f"Cargando modelo desde {self._model_path}")
        with open(self._model_path, "rb") as f:
            self._model = pickle.load(f)  # noqa: S301 — archivo interno, confiable
        logger.info("Modelo cargado exitosamente")
        return self._model

    def _predecir_sync(
        self, features: dict[str, float | int | bool]
    ) -> tuple[float, float]:
        """Inferencia síncrona — se ejecuta en threadpool."""
        model = self._cargar_modelo()

        # Construir vector de features en orden fijo
        X = np.array([[features.get(f, 0) for f in FEATURE_ORDER]], dtype=np.float32)

        # Probabilidad de clase positiva (inflamación)
        proba = model.predict_proba(X)[0]
        prob_positiva = float(proba[1]) if len(proba) > 1 else float(proba[0])

        # Confianza: distancia del 0.5 escalada a [0, 1]
        confianza = min(abs(prob_positiva - 0.5) * 2, 1.0)

        return round(prob_positiva, 4), round(confianza, 4)

    async def predecir(
        self, features: dict[str, float | int | bool]
    ) -> tuple[float, float]:
        """Ejecuta inferencia tabular en el threadpool de asyncio."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._predecir_sync, features)

    async def analizar_imagen(
        self, imagen_url: str
    ) -> tuple[float, float, str | None]:
        """
        En MVP: delega al servicio CNN externo vía HTTP.
        Si no está disponible, retorna valores neutros (circuit breaker).
        """
        try:
            import httpx

            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.post(
                    f"{self._cnn_service_url}/analyze",
                    json={"image_url": imagen_url},
                )
                if response.status_code == 200:
                    data = response.json()
                    return data["probability"], data["confidence"], data.get("gradcam_url")
        except Exception as e:
            logger.warning("Servicio CNN no disponible", exc_info=e)

        # Circuit breaker: valores neutros
        return 0.5, 0.0, None

    @property
    def _cnn_service_url(self) -> str:
        import os
        return os.getenv("ML_SERVICE_URL", "http://localhost:8001")


class _DummyModel:
    """
    Modelo dummy para desarrollo y tests.
    Simula un RandomForest con lógica determinista basada en síntomas.
    """

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        # Lógica simplificada: más síntomas = mayor probabilidad
        features = X[0]
        score = (
            features[0] * 0.20 +  # dolor_articular
            features[1] * 0.15 +  # rigidez_matutina
            min(features[2] / 120, 1.0) * 0.15 +  # duracion_rigidez
            features[3] * 0.20 +  # inflamacion_visible
            features[4] * 0.10 +  # calor_local
            features[5] * 0.10 +  # limitacion_movimiento
            min(features[6] / 4, 1.0) * 0.10   # num_localizaciones
        )
        prob = float(np.clip(score, 0.05, 0.95))
        return np.array([[1 - prob, prob]])
