"""
PrevencionApp — Entidades del Dominio.
Capa más interna de la arquitectura hexagonal.
Sin dependencias externas — solo Python puro.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class NivelRiesgo(str, Enum):
    BAJO = "bajo"
    MODERADO = "moderado"
    ALTO = "alto"
    CRITICO = "critico"


@dataclass
class Sintomas:
    """Value Object — síntomas clínicos estandarizados."""
    dolor_articular: bool
    rigidez_matutina: bool
    duracion_rigidez_minutos: int
    localizacion: list[str]  # ["mano_derecha", "muneca_izquierda", ...]
    inflamacion_visible: bool
    calor_local: bool
    limitacion_movimiento: bool

    def __post_init__(self) -> None:
        if self.duracion_rigidez_minutos < 0:
            raise ValueError("La duración de la rigidez no puede ser negativa")
        if self.duracion_rigidez_minutos > 1440:  # 24h max
            raise ValueError("Duración de rigidez excede 24 horas")


@dataclass
class Formulario:
    """Entidad raíz — representa una evaluación clínica completa."""
    id: UUID = field(default_factory=uuid4)
    paciente_id: UUID | None = None
    fecha: datetime = field(default_factory=datetime.utcnow)
    sintomas: Sintomas | None = None
    imagen_url: str | None = None
    consentimiento: bool = False
    version_cuestionario: str = "1.0"

    # Datos demográficos básicos (anonimizados en MVP)
    edad: int | None = None
    sexo: str | None = None
    pais_id: int | None = None

    def validar(self) -> bool:
        """Invariante del dominio: no se procesa sin consentimiento."""
        if not self.consentimiento:
            return False
        if self.sintomas is None:
            return False
        if self.edad is not None and (self.edad < 0 or self.edad > 120):
            return False
        return True

    def tiene_imagen(self) -> bool:
        return self.imagen_url is not None and len(self.imagen_url) > 0


@dataclass
class ResultadoML:
    """Value Object — resultado de la inferencia de modelos ML."""
    nivel_riesgo: NivelRiesgo
    probabilidad: float  # 0.0 – 1.0
    confianza: float     # confianza del modelo
    gradcam_url: str | None = None
    features_importantes: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.probabilidad <= 1.0:
            raise ValueError("Probabilidad debe estar entre 0 y 1")
        if not 0.0 <= self.confianza <= 1.0:
            raise ValueError("Confianza debe estar entre 0 y 1")

    @property
    def es_confiable(self) -> bool:
        return self.confianza >= 0.70  # threshold configurable

    def recomendacion(self) -> str:
        recomendaciones = {
            NivelRiesgo.BAJO: (
                "Sus síntomas no sugieren inflamación sinovial activa. "
                "Continúe con controles rutinarios."
            ),
            NivelRiesgo.MODERADO: (
                "Se detectaron indicadores de posible inflamación. "
                "Se recomienda consultar con un reumatólogo en los próximos 30 días."
            ),
            NivelRiesgo.ALTO: (
                "Alta probabilidad de inflamación sinovial activa. "
                "Consulte con un reumatólogo a la brevedad (menos de 7 días)."
            ),
            NivelRiesgo.CRITICO: (
                "Indicadores críticos detectados. "
                "Acuda a urgencias o consulte un reumatólogo hoy mismo."
            ),
        }
        return recomendaciones[self.nivel_riesgo]


@dataclass
class EvaluacionTemporal:
    """
    Entidad — evaluación anónima antes de autenticación.
    Vinculada al usuario después del registro/login.
    """
    id: UUID = field(default_factory=uuid4)
    session_id: str = field(default_factory=lambda: str(uuid4()))
    formulario: Formulario | None = None
    resultado: ResultadoML | None = None
    fecha_creacion: datetime = field(default_factory=datetime.utcnow)
    fecha_expiracion: datetime | None = None
    user_id: UUID | None = None  # None = anónima, UUID = vinculada
    imagen_path_temp: str | None = None

    def esta_vinculada(self) -> bool:
        return self.user_id is not None

    def esta_expirada(self) -> bool:
        if self.fecha_expiracion is None:
            return False
        return datetime.utcnow() > self.fecha_expiracion


@dataclass
class Paciente:
    """Entidad — datos demográficos del paciente autenticado."""
    id: UUID = field(default_factory=uuid4)
    user_id: UUID | None = None
    primer_nombre: str = ""
    primer_apellido: str = ""
    # PII hasheada — nunca en texto plano
    identificacion_hash: str = ""
    telefono_hash: str = ""
    direccion: bytes | None = None  # BYTEA para cifrado futuro pgcrypto
    fecha_nacimiento: datetime | None = None
    sexo_id: int | None = None
    pais_id: int | None = None
    ciudad_id: int | None = None
    activo: bool = True
    fecha_creacion: datetime = field(default_factory=datetime.utcnow)
    fecha_actualizacion: datetime = field(default_factory=datetime.utcnow)

    def nombre_completo(self) -> str:
        return f"{self.primer_nombre} {self.primer_apellido}".strip()

    def validar(self) -> bool:
        return bool(self.primer_nombre and self.primer_apellido and self.user_id)
