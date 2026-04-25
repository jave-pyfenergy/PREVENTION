"""
PrevencionApp — Script de entrenamiento del modelo dummy.
Genera un modelo RandomForest realista con datos sintéticos
para desarrollo y pruebas sin datos clínicos reales.

Ejecutar: python scripts/train_dummy_model.py
Salida:   backend/models/model.pkl
"""
import os
import pickle
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

# ── Configuración ─────────────────────────────────────────────────────────────
RANDOM_STATE = 42
N_SAMPLES = 2000
OUTPUT_PATH = Path(__file__).parent.parent / "backend" / "models" / "model.pkl"

# Orden de features — debe coincidir con sklearn_adapter.py::FEATURE_ORDER
FEATURE_NAMES = [
    "dolor_articular",
    "rigidez_matutina",
    "duracion_rigidez_minutos",
    "inflamacion_visible",
    "calor_local",
    "limitacion_movimiento",
    "num_localizaciones",
    "edad",
]


def generar_datos_sinteticos(n: int = N_SAMPLES) -> tuple:
    """
    Genera datos sintéticos basados en la literatura clínica reumatológica.
    Las correlaciones síntoma→diagnóstico son aproximaciones educativas.
    """
    np.random.seed(RANDOM_STATE)

    # Features
    dolor_articular = np.random.binomial(1, 0.65, n)
    rigidez_matutina = np.random.binomial(1, 0.55, n)
    duracion_rigidez = np.random.exponential(45, n).clip(0, 480)  # minutos
    inflamacion_visible = np.random.binomial(1, 0.40, n)
    calor_local = np.random.binomial(1, 0.35, n)
    limitacion_movimiento = np.random.binomial(1, 0.45, n)
    num_localizaciones = np.random.poisson(2.5, n).clip(0, 8)
    edad = np.random.normal(50, 15, n).clip(18, 85)

    X = np.column_stack([
        dolor_articular,
        rigidez_matutina,
        duracion_rigidez,
        inflamacion_visible,
        calor_local,
        limitacion_movimiento,
        num_localizaciones,
        edad,
    ])

    # Label: inflamación sinovial positiva
    # Score basado en combinación clínica (simplificado)
    score = (
        dolor_articular * 0.25 +
        rigidez_matutina * 0.20 +
        (duracion_rigidez / 120).clip(0, 1) * 0.15 +
        inflamacion_visible * 0.20 +
        calor_local * 0.10 +
        limitacion_movimiento * 0.10 +
        (num_localizaciones / 4).clip(0, 1) * 0.10 +
        # Factor edad (riesgo mayor después de 40)
        np.where(edad > 40, 0.05, 0.0)
    )

    # Añadir ruido realista
    score += np.random.normal(0, 0.08, n)
    y = (score > 0.45).astype(int)

    print(f"Dataset generado: {n} muestras | Prevalencia: {y.mean():.1%}")
    return X, y


def entrenar_modelo(X: np.ndarray, y: np.ndarray) -> Pipeline:
    """Entrena pipeline RandomForest con preprocesamiento."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=10,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )),
    ])

    pipeline.fit(X_train, y_train)

    # Evaluación
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_proba)

    print("\n── Métricas del modelo ──────────────────────────")
    print(classification_report(y_test, y_pred, target_names=["Sin inflamación", "Con inflamación"]))
    print(f"ROC-AUC: {auc:.4f}")

    # Feature importance
    rf = pipeline.named_steps["classifier"]
    importances = sorted(
        zip(FEATURE_NAMES, rf.feature_importances_),
        key=lambda x: x[1], reverse=True,
    )
    print("\n── Feature importances ──────────────────────────")
    for feat, imp in importances:
        bar = "█" * int(imp * 40)
        print(f"  {feat:<30} {imp:.4f} {bar}")

    return pipeline


def guardar_modelo(pipeline: Pipeline, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(pipeline, f, protocol=pickle.HIGHEST_PROTOCOL)
    size_kb = path.stat().st_size / 1024
    print(f"\n✅ Modelo guardado en: {path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    print("PrevencionApp — Entrenamiento modelo dummy")
    print("=" * 50)

    X, y = generar_datos_sinteticos()
    model = entrenar_modelo(X, y)
    guardar_modelo(model, OUTPUT_PATH)

    print("\n⚠️  Este es un modelo de desarrollo con datos sintéticos.")
    print("    Reemplazar con modelo entrenado sobre datos clínicos reales en producción.")
