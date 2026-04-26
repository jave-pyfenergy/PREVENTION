"""
PrevencionApp — Puertos (interfaces abstractas) de la capa de Aplicación.
Los adaptadores en la capa de infraestructura implementan estas interfaces.
Principio de inversión de dependencias (SOLID — D).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.application.dto.dtos import (
    HistorialItem,
    PacienteDTO,
    RequestRegistrarPaciente,
)
from app.domain.entities.entities import EvaluacionTemporal, Paciente


class RepositorioPort(ABC):
    """Puerto de persistencia — abstrae Supabase/PostgreSQL."""

    @abstractmethod
    async def guardar_evaluacion_temporal(
        self, evaluacion: EvaluacionTemporal
    ) -> EvaluacionTemporal:
        ...

    @abstractmethod
    async def obtener_evaluacion_por_session(
        self, session_id: str
    ) -> EvaluacionTemporal | None:
        ...

    @abstractmethod
    async def obtener_evaluacion_por_id(
        self, evaluacion_id: UUID
    ) -> EvaluacionTemporal | None:
        ...

    @abstractmethod
    async def vincular_evaluacion_a_usuario(
        self, evaluacion_id: UUID, user_id: UUID
    ) -> None:
        ...

    @abstractmethod
    async def obtener_historial(
        self, user_id: UUID, page: int, page_size: int
    ) -> tuple[list[HistorialItem], int]:
        ...

    @abstractmethod
    async def registrar_paciente_full(
        self,
        user_id: UUID,
        request: RequestRegistrarPaciente,
        identificacion_hash: str,
        telefono_hash: str | None,
    ) -> UUID:
        ...

    @abstractmethod
    async def obtener_paciente(self, user_id: UUID) -> PacienteDTO | None:
        ...


class MLModelPort(ABC):
    """Puerto del modelo de ML — abstrae scikit-learn/ONNX/Vertex AI."""

    @abstractmethod
    async def predecir(
        self,
        features: dict[str, float | int | bool],
    ) -> tuple[float, float, dict[str, float]]:
        """Retorna (probabilidad, confianza, features_importantes)."""
        ...

    @abstractmethod
    async def analizar_imagen(
        self, imagen_url: str
    ) -> tuple[float, float, str | None]:
        """Retorna (probabilidad_cnn, confianza_cnn, gradcam_url)."""
        ...

    def esta_disponible(self) -> bool:
        """Retorna True si el modelo está cargado en memoria."""
        return False

    def cargar_modelo(self) -> None:
        """Pre-carga el modelo. Implementaciones opcionales para pre-warming."""


class StoragePort(ABC):
    """Puerto de almacenamiento — abstrae Supabase Storage / GCS."""

    @abstractmethod
    async def generar_signed_url_subida(
        self, bucket: str, path: str, ttl_seconds: int = 300
    ) -> str:
        ...

    @abstractmethod
    async def mover_imagen_a_permanente(
        self, path_temp: str, user_id: UUID
    ) -> str:
        """Mueve imagen de temp_images a permanent_images/{user_id}/. Retorna nuevo path."""
        ...

    @abstractmethod
    async def eliminar_imagen(self, bucket: str, path: str) -> None:
        ...


class HasherPort(ABC):
    """Puerto de hashing — abstrae SHA-256 + sal dinámica."""

    @abstractmethod
    async def hashear(self, valor: str) -> str:
        """Retorna hex SHA-256 con sal."""
        ...

    @abstractmethod
    async def verificar(self, valor: str, hash_almacenado: str) -> bool:
        ...
