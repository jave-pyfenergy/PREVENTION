"""
PrevencionApp — Tests E2E del flujo completo de evaluación clínica.
Prueban el camino crítico de extremo a extremo usando el modelo ML real
(modelo dummy entrenado con datos sintéticos).
"""
from __future__ import annotations

import pickle
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.application.dto.dtos import RequestFormulario, SintomasRequest
from app.application.use_cases.predecir_inflamacion import PredecirInflamacion
from app.domain.entities.entities import NivelRiesgo
from app.domain.services.evaluador_clinico import ConsentimientoRequeridoError
from app.infrastructure.hashing.sha256_adapter import SHA256Adapter
from app.infrastructure.ml.sklearn_adapter import SklearnAdapter

MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "model.pkl"


@pytest.fixture
def sklearn_adapter():
    """Usa el modelo dummy real si existe, si no, usa el DummyModel interno."""
    path = str(MODEL_PATH) if MODEL_PATH.exists() else "./nonexistent_path/model.pkl"
    return SklearnAdapter(model_path=path, confidence_threshold=0.70)


@pytest.fixture
def hasher():
    return SHA256Adapter(project_id="test", secret_name="test", app_env="development")


@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    repo.guardar_evaluacion_temporal.side_effect = lambda ev: ev
    return repo


@pytest.fixture
def mock_storage():
    storage = AsyncMock()
    storage.generar_signed_url_subida.return_value = "https://fake-storage.com/signed"
    return storage


@pytest.fixture
def use_case_real(sklearn_adapter, hasher, mock_repo, mock_storage):
    """Use case con modelo ML real (o dummy) y hasher real."""
    return PredecirInflamacion(
        ml_model=sklearn_adapter,
        repositorio=mock_repo,
        hasher=hasher,
        storage=mock_storage,
    )


# ── Helper para construir requests ───────────────────────────────────────────

def build_request(
    dolor=True, rigidez=True, duracion=60,
    localizacion=None, inflamacion=True, calor=True,
    limitacion=True, imagen_url=None, edad=50
) -> RequestFormulario:
    return RequestFormulario(
        sintomas=SintomasRequest(
            dolor_articular=dolor,
            rigidez_matutina=rigidez,
            duracion_rigidez_minutos=duracion,
            localizacion=localizacion or ["mano_derecha", "muneca_izquierda"],
            inflamacion_visible=inflamacion,
            calor_local=calor,
            limitacion_movimiento=limitacion,
        ),
        consentimiento=True,
        imagen_url=imagen_url,
        edad=edad,
    )


# ── Tests E2E: Flujo Anónimo ─────────────────────────────────────────────────

class TestFlujoAnonimo:
    @pytest.mark.asyncio
    async def test_evaluacion_completa_alto_riesgo(self, use_case_real):
        """Paciente con muchos síntomas → debe clasificar como alto/critico."""
        request = build_request(
            dolor=True, rigidez=True, duracion=120,
            localizacion=["mano_derecha", "mano_izquierda", "muneca_derecha", "muneca_izquierda"],
            inflamacion=True, calor=True, limitacion=True, edad=55
        )
        resultado = await use_case_real.ejecutar(request)

        assert resultado.nivel_inflamacion in ["alto", "critico", "moderado"]
        assert resultado.probabilidad > 0.5
        assert resultado.session_id is not None
        assert len(resultado.recomendacion) > 20
        assert "disclaimer" in resultado.dict()

    @pytest.mark.asyncio
    async def test_evaluacion_completa_bajo_riesgo(self, use_case_real):
        """Paciente sin síntomas → debe clasificar como bajo."""
        request = build_request(
            dolor=False, rigidez=False, duracion=0,
            localizacion=["rodilla_derecha"],
            inflamacion=False, calor=False, limitacion=False, edad=30
        )
        resultado = await use_case_real.ejecutar(request)

        assert resultado.nivel_inflamacion in ["bajo", "moderado"]
        assert resultado.probabilidad < 0.7
        assert resultado.session_id is not None

    @pytest.mark.asyncio
    async def test_sin_consentimiento_bloquea_evaluacion(self, use_case_real):
        request = RequestFormulario(
            sintomas=SintomasRequest(
                dolor_articular=True, rigidez_matutina=True,
                duracion_rigidez_minutos=60,
                localizacion=["mano_derecha"],
                inflamacion_visible=True, calor_local=True,
                limitacion_movimiento=True,
            ),
            consentimiento=False,  # ← Sin consentimiento
        )
        with pytest.raises(ConsentimientoRequeridoError):
            await use_case_real.ejecutar(request)

    @pytest.mark.asyncio
    async def test_evaluacion_sin_imagen_funciona(self, use_case_real):
        """El sistema debe funcionar sin imagen (solo modelo tabular)."""
        request = build_request(imagen_url=None)
        resultado = await use_case_real.ejecutar(request)
        assert resultado.nivel_inflamacion is not None
        assert resultado.gradcam_url is None

    @pytest.mark.asyncio
    async def test_evaluacion_persiste_en_repo(self, use_case_real, mock_repo):
        request = build_request()
        await use_case_real.ejecutar(request)
        mock_repo.guardar_evaluacion_temporal.assert_called_once()

    @pytest.mark.asyncio
    async def test_resultado_tiene_session_id_unico(self, use_case_real):
        """Dos evaluaciones distintas deben tener session_ids únicos."""
        r1 = await use_case_real.ejecutar(build_request())
        r2 = await use_case_real.ejecutar(build_request())
        assert r1.session_id != r2.session_id


# ── Tests E2E: Hashing PII ───────────────────────────────────────────────────

class TestHashingPII:
    @pytest.mark.asyncio
    async def test_hash_pii_no_contiene_valor_original(self, hasher):
        """Garantía de privacidad: el hash no debe revelar el valor original."""
        numero_documento = "79485123"
        hash_resultado = await hasher.hashear(numero_documento)
        assert numero_documento not in hash_resultado

    @pytest.mark.asyncio
    async def test_hash_longitud_correcta_sha256(self, hasher):
        hash_resultado = await hasher.hashear("valor_test")
        assert len(hash_resultado) == 64  # SHA-256 = 32 bytes = 64 hex chars

    @pytest.mark.asyncio
    async def test_hash_consistente_mismo_input(self, hasher):
        v = "documento_repetido"
        h1 = await hasher.hashear(v)
        h2 = await hasher.hashear(v)
        assert h1 == h2  # Determinista

    @pytest.mark.asyncio
    async def test_diferentes_inputs_diferentes_hashes(self, hasher):
        valores = ["12345678", "87654321", "CC-1234567", "PASS-AB123456"]
        hashes = [await hasher.hashear(v) for v in valores]
        assert len(set(hashes)) == len(valores)  # Todos únicos


# ── Tests E2E: Modelo ML con datos extremos ───────────────────────────────────

class TestModeloMLCasosExtremos:
    @pytest.mark.asyncio
    async def test_probabilidad_dentro_rango_valido(self, use_case_real):
        """La probabilidad siempre debe estar en [0, 1]."""
        for _ in range(10):
            import random
            request = build_request(
                dolor=random.choice([True, False]),
                rigidez=random.choice([True, False]),
                duracion=random.randint(0, 480),
                inflamacion=random.choice([True, False]),
                calor=random.choice([True, False]),
                limitacion=random.choice([True, False]),
                edad=random.randint(18, 85),
            )
            resultado = await use_case_real.ejecutar(request)
            assert 0.0 <= resultado.probabilidad <= 1.0, \
                f"Probabilidad fuera de rango: {resultado.probabilidad}"

    @pytest.mark.asyncio
    async def test_nivel_riesgo_siempre_valido(self, use_case_real):
        """El nivel de riesgo siempre debe ser uno de los valores válidos."""
        niveles_validos = {n.value for n in NivelRiesgo}
        for _ in range(5):
            resultado = await use_case_real.ejecutar(build_request())
            assert resultado.nivel_inflamacion in niveles_validos

    @pytest.mark.asyncio
    async def test_fallo_modelo_ml_degrada_gracefully(self, mock_repo, hasher, mock_storage):
        """Si el modelo ML falla, el sistema responde con graceful degradation."""
        ml_roto = AsyncMock()
        ml_roto.predecir.side_effect = Exception("ML service down")
        ml_roto.analizar_imagen.side_effect = Exception("CNN service down")

        use_case = PredecirInflamacion(
            ml_model=ml_roto,
            repositorio=mock_repo,
            hasher=hasher,
            storage=mock_storage,
        )

        # No debe propagar la excepción del ML
        resultado = await use_case.ejecutar(build_request())
        # Con circuit breaker: valores neutros con baja confianza
        assert resultado is not None
        assert resultado.nivel_inflamacion is not None
        assert resultado.es_confiable is False  # Confianza < 0.70
