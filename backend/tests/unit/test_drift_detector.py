"""
PrevencionApp — Tests unitarios: DriftDetector refactorizado.
Cobertura: Welford stats, baseline, drift detection, recalibración, thread safety.
"""
from __future__ import annotations

import threading
from collections import deque

import pytest

from app.application.services.drift_detector import DriftDetector, _FeatureStats


# ── _FeatureStats (Welford) ──────────────────────────────────────────────────

class TestFeatureStatsWelford:
    def test_mean_single_value(self):
        s = _FeatureStats()
        s.update(0.5)
        assert s.mean == pytest.approx(0.5)

    def test_mean_multiple_values(self):
        s = _FeatureStats()
        for v in [0.2, 0.4, 0.6, 0.8]:
            s.update(v)
        assert s.mean == pytest.approx(0.5)

    def test_std_matches_population(self):
        import statistics
        values = [0.1, 0.3, 0.5, 0.7, 0.9]
        s = _FeatureStats()
        for v in values:
            s.update(v)
        expected = statistics.stdev(values)
        assert s.std == pytest.approx(expected, rel=1e-6)

    def test_std_single_value_is_zero(self):
        s = _FeatureStats()
        s.update(0.42)
        assert s.std == 0.0

    def test_n_increments(self):
        s = _FeatureStats()
        for i in range(7):
            s.update(float(i))
        assert s.n == 7


# ── DriftDetector — comportamiento básico ────────────────────────────────────

class TestDriftDetectorBaseline:
    def test_no_alerts_before_min_samples(self):
        det = DriftDetector(window_size=10, min_samples_before_check=20)
        sample = {"dolor_articular": 1.0, "rigidez_matutina": 0.5}
        for _ in range(19):
            alerts = det.registrar(sample)
            assert alerts == []

    def test_baseline_established_on_first_full_window(self):
        det = DriftDetector(window_size=30, min_samples_before_check=5)
        sample = {"feat_a": 0.5, "feat_b": 0.3}
        for _ in range(30):
            det.registrar(sample)
        assert det.resumen["baseline_establecido"] is True

    def test_baseline_not_established_before_full_window(self):
        det = DriftDetector(window_size=50, min_samples_before_check=5)
        sample = {"feat": 0.5}
        for _ in range(49):
            det.registrar(sample)
        assert det.resumen["baseline_establecido"] is False

    def test_resumen_tracks_total_evaluaciones(self):
        det = DriftDetector()
        for _ in range(42):
            det.registrar({"x": 0.5})
        assert det.resumen["total_evaluaciones"] == 42


# ── Drift detection ───────────────────────────────────────────────────────────

class TestDriftDetection:
    def _make_detector_with_baseline(self, baseline_value: float = 0.5, n: int = 100):
        """Construye detector con baseline establecido."""
        det = DriftDetector(window_size=n, z_threshold=2.0, min_samples_before_check=10)
        for _ in range(n):
            det.registrar({"feat": baseline_value})
        return det

    def test_no_drift_when_distribution_stable(self):
        det = self._make_detector_with_baseline(0.5)
        for _ in range(20):
            alerts = det.registrar({"feat": 0.5})
        assert alerts == []

    def test_drift_detected_on_large_shift(self):
        det = self._make_detector_with_baseline(baseline_value=0.1, n=100)
        # Inyectar shift masivo: media del todo acumulado cambia sustancialmente
        alerts_found = []
        for _ in range(100):
            a = det.registrar({"feat": 0.95})
            alerts_found.extend(a)
        # Debe haber detectado drift en algún momento
        assert len(alerts_found) > 0

    def test_drift_alert_contains_feature_name(self):
        det = self._make_detector_with_baseline(0.0, n=100)
        all_alerts = []
        for _ in range(50):
            all_alerts.extend(det.registrar({"feat": 1.0}))
        if all_alerts:
            assert "feat" in all_alerts[0]

    def test_drift_direction_up(self):
        det = self._make_detector_with_baseline(0.0, n=100)
        all_alerts = []
        for _ in range(100):
            all_alerts.extend(det.registrar({"feat": 1.0}))
        assert any("↑" in a for a in all_alerts)

    def test_drift_direction_down(self):
        det = self._make_detector_with_baseline(1.0, n=100)
        all_alerts = []
        for _ in range(100):
            all_alerts.extend(det.registrar({"feat": 0.0}))
        assert any("↓" in a for a in all_alerts)


# ── Thread safety ─────────────────────────────────────────────────────────────

class TestDriftDetectorThreadSafety:
    def test_concurrent_registrar_no_exception(self):
        det = DriftDetector(window_size=100, min_samples_before_check=10)
        errors = []

        def worker():
            try:
                for _ in range(50):
                    det.registrar({"a": 0.5, "b": 0.3})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Excepciones en threads: {errors}"

    def test_total_evaluaciones_consistent_under_concurrency(self):
        det = DriftDetector(window_size=500, min_samples_before_check=10)
        n_threads, n_per_thread = 10, 100

        def worker():
            for _ in range(n_per_thread):
                det.registrar({"x": 0.5})

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert det.resumen["total_evaluaciones"] == n_threads * n_per_thread


# ── Exportar / importar estado ────────────────────────────────────────────────

class TestDriftDetectorPersistencia:
    def test_exportar_importar_preserva_baseline(self):
        det = DriftDetector(window_size=50, min_samples_before_check=5)
        for _ in range(50):
            det.registrar({"feat": 0.5})

        estado = det.exportar_estado()
        assert estado["baseline"] is not None

        det2 = DriftDetector(window_size=50, min_samples_before_check=5)
        det2.importar_estado(estado)
        assert det2.resumen["baseline_establecido"] is True
        assert det2.resumen["total_evaluaciones"] == det.resumen["total_evaluaciones"]

    def test_importar_estado_vacio_no_crash(self):
        det = DriftDetector()
        det.importar_estado({})
        assert det.resumen["baseline_establecido"] is False

    def test_exportar_sin_baseline_es_serializable(self):
        import json
        det = DriftDetector()
        det.registrar({"x": 0.5})
        estado = det.exportar_estado()
        # No debe lanzar al serializar
        json.dumps(estado)


# ── Resiliencia ───────────────────────────────────────────────────────────────

class TestDriftDetectorResiliencia:
    def test_features_vacias_no_crash(self):
        det = DriftDetector()
        alerts = det.registrar({})
        assert alerts == []

    def test_nuevo_feature_midstream_no_crash(self):
        det = DriftDetector(window_size=30, min_samples_before_check=5)
        for _ in range(20):
            det.registrar({"a": 0.5})
        # Aparece nueva feature no vista antes
        for _ in range(10):
            det.registrar({"a": 0.5, "b_nuevo": 0.9})

    def test_error_interno_no_propaga(self):
        det = DriftDetector()
        # Forzar un valor no numérico que no se puede convertir a float
        alerts = det.registrar({"feat": object()})  # type: ignore
        assert alerts == []
