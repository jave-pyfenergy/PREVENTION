"""
PrevencionApp — DTOs de la capa de Aplicación.
Contratos de entrada/salida entre la API y los casos de uso.
Validación estricta con Pydantic v2.
"""

import re
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Patrón para validar imagen_url — solo permite URLs de Supabase Storage
_SUPABASE_STORAGE_RE = re.compile(
    r'^https://[a-z0-9-]+\.supabase\.co/storage/v1/object/'
)


# ── Request DTOs ──────────────────────────────────────────────────────────────

class SintomasRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    dolor_articular: bool
    rigidez_matutina: bool
    duracion_rigidez_minutos: Annotated[int, Field(ge=0, le=1440)]
    localizacion: list[str] = Field(min_length=1, max_length=20)
    inflamacion_visible: bool
    calor_local: bool
    limitacion_movimiento: bool

    @field_validator("localizacion")
    @classmethod
    def validar_localizacion(cls, v: list[str]) -> list[str]:
        opciones_validas = {
            "mano_derecha", "mano_izquierda", "muneca_derecha", "muneca_izquierda",
            "codo_derecho", "codo_izquierdo", "rodilla_derecha", "rodilla_izquierda",
            "tobillo_derecho", "tobillo_izquierdo", "pie_derecho", "pie_izquierdo",
            "cadera_derecha", "cadera_izquierda", "hombro_derecho", "hombro_izquierdo",
        }
        for loc in v:
            if loc not in opciones_validas:
                raise ValueError(f"Localización inválida: {loc}")
        return v


class RequestFormulario(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    sintomas: SintomasRequest
    imagen_url: str | None = Field(default=None, max_length=2048)
    consentimiento: bool

    @field_validator("imagen_url")
    @classmethod
    def validar_imagen_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _SUPABASE_STORAGE_RE.match(v):
            raise ValueError(
                "imagen_url debe apuntar a Supabase Storage "
                "(https://<proyecto>.supabase.co/storage/v1/object/...)"
            )
        return v
    version_cuestionario: str = Field(default="1.0", max_length=10)

    # Demográficos básicos (opcionales en flujo anónimo)
    edad: Annotated[int, Field(ge=0, le=120)] | None = None
    sexo: str | None = Field(default=None, max_length=20)
    pais_id: int | None = None

    @field_validator("consentimiento")
    @classmethod
    def validar_consentimiento(cls, v: bool) -> bool:
        if not v:
            raise ValueError("El consentimiento informado es obligatorio")
        return v


class RequestVincularEvaluacion(BaseModel):
    evaluacion_id: UUID
    user_id: UUID


class RequestRegistrarPaciente(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    primer_nombre: str = Field(min_length=1, max_length=100)
    primer_apellido: str = Field(min_length=1, max_length=100)
    segundo_nombre: str | None = Field(default=None, max_length=100)
    segundo_apellido: str | None = Field(default=None, max_length=100)
    identificacion: str = Field(min_length=5, max_length=50)
    tipo_identificacion_id: int
    telefono: str | None = Field(default=None, max_length=20)
    fecha_nacimiento: datetime | None = None
    sexo_id: int | None = None
    pais_id: int | None = None
    ciudad_id: int | None = None


# ── Response DTOs ─────────────────────────────────────────────────────────────

class ResponsePrediccion(BaseModel):
    evaluacion_id: UUID
    session_id: str
    nivel_inflamacion: str
    probabilidad: float = Field(ge=0.0, le=1.0)
    confianza: float = Field(ge=0.0, le=1.0)
    es_confiable: bool
    gradcam_url: str | None = None
    recomendacion: str
    features_importantes: dict[str, float] = Field(
        default_factory=dict,
        description="Contribución normalizada de cada síntoma al resultado (XAI)",
    )
    reglas_clinicas: list[str] = Field(
        default_factory=list,
        description="Reglas clínicas expertas que ajustaron la predicción ML",
    )
    disclaimer: str = (
        "Este análisis es orientativo y no reemplaza el diagnóstico médico. "
        "Consulte siempre con un profesional de salud."
    )
    fecha: datetime


class ResponseSignedUrl(BaseModel):
    signed_url: str
    path: str
    ttl_seconds: int = 300


class PacienteDTO(BaseModel):
    id: UUID
    user_id: UUID
    primer_nombre: str
    primer_apellido: str
    fecha_nacimiento: datetime | None = None
    pais_id: int | None = None
    fecha_creacion: datetime


class HistorialItem(BaseModel):
    evaluacion_id: UUID
    session_id: str
    fecha: datetime
    nivel_inflamacion: str
    probabilidad: float
    tiene_imagen: bool


class ResponseHistorial(BaseModel):
    items: list[HistorialItem]
    total: int
    page: int
    page_size: int
    has_next: bool


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
