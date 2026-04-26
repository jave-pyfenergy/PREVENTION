"""
PrevencionApp — Tests Unitarios.
Prueban la lógica de dominio y casos de uso con mocks de adaptadores.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime

from app.domain.entities.entities import (
    Formulario,
    NivelRiesgo,
    ResultadoML,
    Sintomas,
)
from app.domain.services.evaluador_clinico import (
    ConsentimientoRequeridoError,
    DomainValidationError,
    EvaluadorClinico,
    ValidadorConsentimiento,
)
from app.application.use_cases.predecir_inflamacion import PredecirInflamacion
from app.application.dto.dtos import RequestFormulario, SintomasRequest


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sintomas_alto_riesgo():
    return Sintomas(
        dolor_articular=True,
        rigidez_matutina=True,
        duracion_rigidez_minutos=90,
        localizacion=["mano_derecha", "mano_izquierda", "muneca_derecha"],
        inflamacion_visible=True,
        calor_local=True,
        limitacion_movimiento=True,
    )


@pytest.fixture
def sintomas_bajo_riesgo():
    return Sintomas(
        dolor_articular=False,
        rigidez_matutina=False,
        duracion_rigidez_minutos=0,
        localizacion=["rodilla_derecha"],
        inflamacion_visible=False,
        calor_local=False,
        limitacion_movimiento=False,
    )


@pytest.fixture
def formulario_valido(sintomas_alto_riesgo):
    return Formulario(
        id=uuid4(),
        sintomas=sintomas_alto_riesgo,
        consentimiento=True,
        edad=45,
        sexo="femenino",
    )


@pytest.fixture
def mock_ml():
    ml = AsyncMock()
    ml.predecir.return_value = (0.75, 0.85, {"dolor_articular": 0.35, "rigidez_matutina": 0.25})
    ml.analizar_imagen.return_value = (0.80, 0.90, "https://example.com/gradcam.jpg")
    return ml


@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    repo.guardar_evaluacion_temporal.side_effect = lambda ev: ev
    return repo


@pytest.fixture
def mock_hasher():
    hasher = AsyncMock()
    hasher.hashear.return_value = "a" * 64
    hasher.verificar.return_value = True
    return hasher


@pytest.fixture
def mock_storage():
    storage = AsyncMock()
    storage.generar_signed_url_subida.return_value = "https://storage.example.com/signed"
    storage.mover_imagen_a_permanente.return_value = "user123/imagen.jpg"
    return storage


# ── Tests: Entidades de Dominio ───────────────────────────────────────────────

class TestFormulario:
    def test_formulario_valido_con_consentimiento(self, formulario_valido):
        assert formulario_valido.validar() is True

    def test_formulario_invalido_sin_consentimiento(self, sintomas_alto_riesgo):
        f = Formulario(sintomas=sintomas_alto_riesgo, consentimiento=False)
        assert f.validar() is False

    def test_formulario_sin_sintomas_invalido(self):
        f = Formulario(consentimiento=True, sintomas=None)
        assert f.validar() is False

    def test_formulario_edad_invalida(self, sintomas_bajo_riesgo):
        f = Formulario(sintomas=sintomas_bajo_riesgo, consentimiento=True, edad=200)
        assert f.validar() is False

    def test_formulario_con_imagen(self, formulario_valido):
        formulario_valido.imagen_url = "https://example.com/image.jpg"
        assert formulario_valido.tiene_imagen() is True

    def test_formulario_sin_imagen(self, formulario_valido):
        formulario_valido.imagen_url = None
        assert formulario_valido.tiene_imagen() is False


class TestSintomas:
    def test_duracion_negativa_invalida(self):
        with pytest.raises(ValueError, match="negativa"):
            Sintomas(
                dolor_articular=True,
                rigidez_matutina=True,
                duracion_rigidez_minutos=-1,
                localizacion=["mano_derecha"],
                inflamacion_visible=False,
                calor_local=False,
                limitacion_movimiento=False,
            )

    def test_duracion_maxima_invalida(self):
        with pytest.raises(ValueError):
            Sintomas(
                dolor_articular=True,
                rigidez_matutina=True,
                duracion_rigidez_minutos=1500,  # >24h
                localizacion=["mano_derecha"],
                inflamacion_visible=False,
                calor_local=False,
                limitacion_movimiento=False,
            )


class TestResultadoML:
    def test_probabilidad_invalida(self):
        with pytest.raises(ValueError):
            ResultadoML(
                nivel_riesgo=NivelRiesgo.ALTO,
                probabilidad=1.5,  # >1.0
                confianza=0.8,
            )

    def test_resultado_confiable(self):
        r = ResultadoML(nivel_riesgo=NivelRiesgo.ALTO, probabilidad=0.8, confianza=0.85)
        assert r.es_confiable is True

    def test_resultado_no_confiable(self):
        r = ResultadoML(nivel_riesgo=NivelRiesgo.BAJO, probabilidad=0.3, confianza=0.50)
        assert r.es_confiable is False

    def test_recomendacion_critica(self):
        r = ResultadoML(nivel_riesgo=NivelRiesgo.CRITICO, probabilidad=0.95, confianza=0.90)
        rec = r.recomendacion()
        assert "urgencias" in rec.lower() or "reumatólogo" in rec.lower()


# ── Tests: Servicios de Dominio ───────────────────────────────────────────────

class TestEvaluadorClinico:
    def test_calcular_nivel_bajo(self):
        assert EvaluadorClinico.calcular_nivel(0.15) == NivelRiesgo.BAJO

    def test_calcular_nivel_moderado(self):
        assert EvaluadorClinico.calcular_nivel(0.45) == NivelRiesgo.MODERADO

    def test_calcular_nivel_alto(self):
        assert EvaluadorClinico.calcular_nivel(0.72) == NivelRiesgo.ALTO

    def test_calcular_nivel_critico(self):
        assert EvaluadorClinico.calcular_nivel(0.90) == NivelRiesgo.CRITICO

    def test_fusion_sin_cnn(self):
        prob, conf = EvaluadorClinico.fusionar_predicciones(0.75, None, 0.85, None)
        assert prob == 0.75
        assert conf == 0.85

    def test_fusion_con_cnn(self):
        # 60% tabular + 40% CNN
        prob, conf = EvaluadorClinico.fusionar_predicciones(0.80, 0.70, 0.90, 0.80)
        expected_prob = round(0.60 * 0.80 + 0.40 * 0.70, 4)
        assert prob == expected_prob


class TestValidadorConsentimiento:
    def test_consentimiento_valido(self, formulario_valido):
        # No debe lanzar excepción
        ValidadorConsentimiento.validar(formulario_valido)

    def test_sin_consentimiento_lanza_error(self, sintomas_alto_riesgo):
        f = Formulario(sintomas=sintomas_alto_riesgo, consentimiento=False)
        with pytest.raises(ConsentimientoRequeridoError):
            ValidadorConsentimiento.validar(f)


# ── Tests: Caso de Uso PredecirInflamacion ────────────────────────────────────

class TestPredecirInflamacion:
    @pytest.fixture
    def use_case(self, mock_ml, mock_repo, mock_hasher, mock_storage):
        return PredecirInflamacion(
            ml_model=mock_ml,
            repositorio=mock_repo,
            hasher=mock_hasher,
            storage=mock_storage,
            drift_detector=None,
        )

    @pytest.fixture
    def request_valido(self):
        return RequestFormulario(
            sintomas=SintomasRequest(
                dolor_articular=True,
                rigidez_matutina=True,
                duracion_rigidez_minutos=60,
                localizacion=["mano_derecha", "muneca_izquierda"],
                inflamacion_visible=True,
                calor_local=False,
                limitacion_movimiento=True,
            ),
            consentimiento=True,
            imagen_url="https://abcdefghijklmnop.supabase.co/storage/v1/object/sign/temp/image.jpg",
            edad=40,
        )

    @pytest.mark.asyncio
    async def test_prediccion_exitosa(self, use_case, request_valido):
        resultado = await use_case.ejecutar(request_valido)
        assert resultado.nivel_inflamacion in [n.value for n in NivelRiesgo]
        assert 0 <= resultado.probabilidad <= 1
        assert resultado.session_id is not None
        assert resultado.recomendacion != ""

    @pytest.mark.asyncio
    async def test_sin_consentimiento_lanza_error(self, use_case, request_valido):
        request_valido.consentimiento = False
        with pytest.raises(Exception):
            await use_case.ejecutar(request_valido)

    @pytest.mark.asyncio
    async def test_sin_imagen_usa_solo_tabular(self, use_case, request_valido, mock_ml):
        request_valido.imagen_url = None
        resultado = await use_case.ejecutar(request_valido)
        mock_ml.analizar_imagen.assert_not_called()
        assert resultado is not None

    @pytest.mark.asyncio
    async def test_fallo_cnn_degradacion_graceful(self, use_case, request_valido, mock_ml):
        """Si CNN falla, el sistema responde con solo el modelo tabular."""
        mock_ml.analizar_imagen.side_effect = Exception("CNN service unavailable")
        resultado = await use_case.ejecutar(request_valido)
        # No debe propagar el error
        assert resultado.nivel_inflamacion is not None
        assert resultado.gradcam_url is None

    @pytest.mark.asyncio
    async def test_evaluacion_persistida(self, use_case, request_valido, mock_repo):
        await use_case.ejecutar(request_valido)
        mock_repo.guardar_evaluacion_temporal.assert_called_once()


# ── Tests: SHA256Adapter ──────────────────────────────────────────────────────

class TestSHA256Adapter:
    @pytest.mark.asyncio
    async def test_hash_es_hex_64_chars(self):
        from app.infrastructure.hashing.sha256_adapter import SHA256Adapter
        adapter = SHA256Adapter(project_id="test", secret_name="test", app_env="development")
        resultado = await adapter.hashear("test_valor")
        assert len(resultado) == 64
        assert all(c in "0123456789abcdef" for c in resultado)

    @pytest.mark.asyncio
    async def test_hash_determinista(self):
        from app.infrastructure.hashing.sha256_adapter import SHA256Adapter
        adapter = SHA256Adapter(project_id="test", secret_name="test", app_env="development")
        h1 = await adapter.hashear("mismo_valor")
        h2 = await adapter.hashear("mismo_valor")
        assert h1 == h2

    @pytest.mark.asyncio
    async def test_valores_distintos_hashes_distintos(self):
        from app.infrastructure.hashing.sha256_adapter import SHA256Adapter
        adapter = SHA256Adapter(project_id="test", secret_name="test", app_env="development")
        h1 = await adapter.hashear("valor_1")
        h2 = await adapter.hashear("valor_2")
        assert h1 != h2

    @pytest.mark.asyncio
    async def test_verificacion_correcta(self):
        from app.infrastructure.hashing.sha256_adapter import SHA256Adapter
        adapter = SHA256Adapter(project_id="test", secret_name="test", app_env="development")
        valor = "documento_123456"
        hash_almacenado = await adapter.hashear(valor)
        assert await adapter.verificar(valor, hash_almacenado) is True

    @pytest.mark.asyncio
    async def test_verificacion_incorrecta(self):
        from app.infrastructure.hashing.sha256_adapter import SHA256Adapter
        adapter = SHA256Adapter(project_id="test", secret_name="test", app_env="development")
        hash_almacenado = await adapter.hashear("valor_correcto")
        assert await adapter.verificar("valor_incorrecto", hash_almacenado) is False
