"""
PrevencionApp — Adaptador ML scikit-learn/XGBoost.
Carga el modelo desde disco (dev) o GCS (prod) y ejecuta inferencia tabular.
El análisis CNN está delegado a un servicio separado en producción.
"""
from __future__ import annotations

import asyncio
import logging
import os
import pickle
import threading
from pathlib import Path
from typing import Any

import httpx
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

# Labels en español para XAI
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


class SklearnAdapter(MLModelPort):
    """
    Adaptador para modelos scikit-learn / XGBoost serializados con pickle.
    El modelo se carga lazy (primera inferencia) para optimizar cold start.
    """

    def __init__(self, model_path: str, confidence_threshold: float = 0.70) -> None:
        self._model_path = Path(model_path)
        self._confidence_threshold = confidence_threshold
        self._model: Any = None
        self._load_lock = threading.Lock()

    def _cargar_modelo(self) -> Any:
        """Carga el modelo desde disco. Thread-safe: double-checked locking."""
        if self._model is not None:
            return self._model

        with self._load_lock:
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
    ) -> tuple[float, float, dict[str, float]]:
        """Inferencia síncrona con feature importances — se ejecuta en threadpool."""
        model = self._cargar_modelo()

        X = np.array([[features.get(f, 0) for f in FEATURE_ORDER]], dtype=np.float32)

        proba = model.predict_proba(X)[0]
        prob_positiva = float(proba[1]) if len(proba) > 1 else float(proba[0])
        confianza = min(abs(prob_positiva - 0.5) * 2, 1.0)

        # Compute feature importances — handle both Pipeline and raw estimators
        importancias: dict[str, float] = {}
        estimator = _extract_tree_estimator(model)
        if estimator is not None and hasattr(estimator, "feature_importances_"):
            raw = {
                name: float(imp)
                for name, imp in zip(FEATURE_ORDER, estimator.feature_importances_)
            }
            total = sum(raw.values()) or 1.0
            importancias = {k: round(v / total, 4) for k, v in raw.items()}
        elif isinstance(model, _DummyModel):
            importancias = model.get_feature_importances(X[0], features)
        else:
            importancias = {name: round(1.0 / len(FEATURE_ORDER), 4) for name in FEATURE_ORDER}

        return round(prob_positiva, 4), round(confianza, 4), importancias

    async def predecir(
        self, features: dict[str, float | int | bool]
    ) -> tuple[float, float, dict[str, float]]:
        """Ejecuta inferencia tabular con importancias en el threadpool de asyncio."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._predecir_sync, features)

    async def analizar_imagen(
        self, imagen_url: str
    ) -> tuple[float, float, str | None]:
        """
        En MVP: delega al servicio CNN externo vía HTTP.
        Si no está disponible, retorna valores neutros (circuit breaker).
        """
        try:
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

        return 0.5, 0.0, None

    @property
    def _cnn_service_url(self) -> str:
        return os.getenv("ML_SERVICE_URL", "http://localhost:8001")


class _DummyModel:
    """
    Modelo dummy para desarrollo y tests.
    Simula un RandomForest con lógica determinista basada en síntomas.
    """

    # Pesos de cada feature en el score final
    _WEIGHTS = [0.20, 0.15, 0.15, 0.20, 0.10, 0.10, 0.10, 0.0]
    # dolor, rigidez, duracion, inflamacion, calor, limitacion, localizaciones, edad

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        features = X[0]
        score = (
            features[0] * 0.20 +            # dolor_articular
            features[1] * 0.15 +            # rigidez_matutina
            min(features[2] / 120, 1.0) * 0.15 +  # duracion_rigidez
            features[3] * 0.20 +            # inflamacion_visible
            features[4] * 0.10 +            # calor_local
            features[5] * 0.10 +            # limitacion_movimiento
            min(features[6] / 4, 1.0) * 0.10   # num_localizaciones
        )
        prob = float(np.clip(score, 0.05, 0.95))
        return np.array([[1 - prob, prob]])

    def get_feature_importances(
        self, X: np.ndarray, raw_features: dict[str, float | int | bool]
    ) -> dict[str, float]:
        """Calcula contribución de cada feature al score normalizada a [0,1]."""
        contributions = {
            "dolor_articular":           float(X[0]) * 0.20,
            "rigidez_matutina":          float(X[1]) * 0.15,
            "duracion_rigidez_minutos":  min(float(X[2]) / 120, 1.0) * 0.15,
            "inflamacion_visible":       float(X[3]) * 0.20,
            "calor_local":               float(X[4]) * 0.10,
            "limitacion_movimiento":     float(X[5]) * 0.10,
            "num_localizaciones":        min(float(X[6]) / 4, 1.0) * 0.10,
            "edad":                      0.0,  # dummy model ignores age
        }
        total = sum(contributions.values()) or 1.0
        return {k: round(v / total, 4) for k, v in contributions.items()}
