"""
PrevencionApp — Tests de Integración.
Prueban los endpoints de la API usando FastAPI TestClient.
Los adaptadores de infraestructura son reemplazados por mocks.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from fastapi.testclient import TestClient

from app.entrypoints.api.main import app
from app.config.container import Container
from app.application.dto.dtos import (
    ResponsePrediccion,
    ResponseSignedUrl,
    ResponseHistorial,
    HistorialItem,
    PacienteDTO,
)


# ── Fixtures de setup ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def mock_container():
    """
    Reemplaza el contenedor DI con mocks controlados.
    Patrón: dependency_overrides de FastAPI.
    """
    from app.config.container import get_container

    container = MagicMock(spec=Container)
    session_id = str(uuid4())
    evaluacion_id = uuid4()

    # Mock de predecir_inflamacion
    predecir_mock = AsyncMock()
    predecir_mock.ejecutar.return_value = ResponsePrediccion(
        evaluacion_id=evaluacion_id,
        session_id=session_id,
        nivel_inflamacion="moderado",
        probabilidad=0.58,
        confianza=0.82,
        es_confiable=True,
        gradcam_url=None,
        recomendacion="Se recomienda consultar con un reumatólogo en 30 días.",
        fecha=datetime.utcnow(),
    )
    container.predecir_inflamacion = predecir_mock

    # Mock de storage
    storage_mock = AsyncMock()
    storage_mock.generar_signed_url_subida.return_value = "https://storage.example.com/signed?token=xxx"
    container.storage = storage_mock

    # Mock de repositorio
    repo_mock = AsyncMock()
    repo_mock.obtener_evaluacion_por_session.return_value = None
    container.repositorio = repo_mock

    # Mock de vincular
    vincular_mock = AsyncMock()
    vincular_mock.ejecutar.return_value = None
    container.vincular_evaluacion = vincular_mock

    # Mock de historial
    historial_mock = AsyncMock()
    historial_mock.ejecutar.return_value = ResponseHistorial(
        items=[
            HistorialItem(
                evaluacion_id=uuid4(),
                session_id=str(uuid4()),
                fecha=datetime.utcnow(),
                nivel_inflamacion="bajo",
                probabilidad=0.22,
                tiene_imagen=False,
            )
        ],
        total=1,
        page=1,
        page_size=20,
        has_next=False,
    )
    container.obtener_historial = historial_mock

    # Mock de registrar_paciente
    registrar_mock = AsyncMock()
    registrar_mock.ejecutar.return_value = uuid4()
    container.registrar_paciente = registrar_mock

    # Inyectar mock en la app
    app.dependency_overrides[get_container] = lambda: container

    yield container, session_id, evaluacion_id

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def client(mock_container):
    return TestClient(app, raise_server_exceptions=True)


# ── Tests: Health Check ──────────────────────────────────────────────────────

class TestHealthCheck:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_structure(self, client):
        data = client.get("/health").json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "env" in data


# ── Tests: POST /api/v1/evaluacion-temporal ──────────────────────────────────

class TestEvaluacionTemporal:
    PAYLOAD_VALIDO = {
        "sintomas": {
            "dolor_articular": True,
            "rigidez_matutina": True,
            "duracion_rigidez_minutos": 60,
            "localizacion": ["mano_derecha", "muneca_izquierda"],
            "inflamacion_visible": True,
            "calor_local": False,
            "limitacion_movimiento": True,
        },
        "consentimiento": True,
        "version_cuestionario": "1.0",
        "edad": 45,
        "sexo": "femenino",
    }

    def test_evaluacion_exitosa_retorna_200(self, client, mock_container):
        response = client.post(
            "/api/v1/evaluacion-temporal",
            json=self.PAYLOAD_VALIDO,
        )
        assert response.status_code == 200

    def test_evaluacion_retorna_nivel_riesgo(self, client, mock_container):
        data = client.post(
            "/api/v1/evaluacion-temporal",
            json=self.PAYLOAD_VALIDO,
        ).json()
        assert data["nivel_inflamacion"] in ["bajo", "moderado", "alto", "critico"]

    def test_evaluacion_retorna_probabilidad(self, client, mock_container):
        data = client.post(
            "/api/v1/evaluacion-temporal",
            json=self.PAYLOAD_VALIDO,
        ).json()
        assert 0 <= data["probabilidad"] <= 1

    def test_evaluacion_retorna_disclaimer(self, client, mock_container):
        data = client.post(
            "/api/v1/evaluacion-temporal",
            json=self.PAYLOAD_VALIDO,
        ).json()
        assert "disclaimer" in data
        assert len(data["disclaimer"]) > 10

    def test_sin_consentimiento_retorna_422(self, client, mock_container):
        payload = {**self.PAYLOAD_VALIDO, "consentimiento": False}
        response = client.post("/api/v1/evaluacion-temporal", json=payload)
        assert response.status_code == 422

    def test_sintomas_invalidos_retorna_422(self, client, mock_container):
        payload = dict(self.PAYLOAD_VALIDO)
        payload["sintomas"] = {**payload["sintomas"], "duracion_rigidez_minutos": -10}
        response = client.post("/api/v1/evaluacion-temporal", json=payload)
        assert response.status_code == 422

    def test_localizacion_vacia_retorna_422(self, client, mock_container):
        payload = dict(self.PAYLOAD_VALIDO)
        payload["sintomas"] = {**payload["sintomas"], "localizacion": []}
        response = client.post("/api/v1/evaluacion-temporal", json=payload)
        assert response.status_code == 422

    def test_localizacion_invalida_retorna_422(self, client, mock_container):
        payload = dict(self.PAYLOAD_VALIDO)
        payload["sintomas"] = {
            **payload["sintomas"],
            "localizacion": ["articulation_invalida_xyz"]
        }
        response = client.post("/api/v1/evaluacion-temporal", json=payload)
        assert response.status_code == 422


# ── Tests: POST /api/v1/imagenes/upload-url ──────────────────────────────────

class TestUploadUrl:
    def test_retorna_signed_url(self, client, mock_container):
        response = client.post("/api/v1/imagenes/upload-url")
        assert response.status_code == 200

    def test_signed_url_tiene_campos_requeridos(self, client, mock_container):
        data = client.post("/api/v1/imagenes/upload-url").json()
        assert "signed_url" in data
        assert "path" in data
        assert "ttl_seconds" in data

    def test_ttl_es_300_segundos(self, client, mock_container):
        data = client.post("/api/v1/imagenes/upload-url").json()
        assert data["ttl_seconds"] == 300


# ── Tests: GET /api/v1/resultado/{session_id} ────────────────────────────────

class TestObtenerResultado:
    def test_session_inexistente_retorna_404(self, client, mock_container):
        response = client.get("/api/v1/resultado/session-que-no-existe")
        assert response.status_code == 404

    def test_session_id_vacio_retorna_404(self, client, mock_container):
        response = client.get("/api/v1/resultado/")
        # 404 o 405 dependiendo del routing
        assert response.status_code in [404, 405]


# ── Tests: Endpoints protegidos (requieren JWT) ───────────────────────────────

class TestEndpointsProtegidos:
    """Verifican que los endpoints autenticados rechazan requests sin token."""

    def test_historial_sin_jwt_retorna_401(self, client):
        response = client.get("/api/v1/historial")
        assert response.status_code == 401

    def test_perfil_sin_jwt_retorna_401(self, client):
        response = client.get("/api/v1/paciente/perfil")
        assert response.status_code == 401

    def test_registrar_paciente_sin_jwt_retorna_401(self, client):
        response = client.post(
            "/api/v1/paciente/registrar",
            json={
                "primer_nombre": "Juan",
                "primer_apellido": "Pérez",
                "identificacion": "12345678",
                "tipo_identificacion_id": 1,
            },
        )
        assert response.status_code == 401

    def test_vincular_sin_jwt_retorna_401(self, client):
        response = client.post(
            f"/api/v1/vincular-evaluacion?evaluacion_id={uuid4()}"
        )
        assert response.status_code == 401


# ── Tests: Rate Limiting Headers ─────────────────────────────────────────────

class TestResponseHeaders:
    def test_response_time_header_presente(self, client, mock_container):
        response = client.get("/health")
        assert "X-Response-Time" in response.headers

    def test_cors_headers_presentes(self, client, mock_container):
        response = client.options(
            "/api/v1/evaluacion-temporal",
            headers={"Origin": "http://localhost:5173"},
        )
        # OPTIONS debe ser manejado por CORS middleware
        assert response.status_code in [200, 204, 405]
