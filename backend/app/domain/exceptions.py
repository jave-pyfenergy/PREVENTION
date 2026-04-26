"""
PrevencionApp — Excepciones del Dominio.
Centralizadas aquí para que cualquier capa las importe sin arrastrar servicios.
"""


class DomainException(Exception):
    """Base para todas las excepciones de dominio."""


class DomainValidationError(DomainException):
    """Invariante de dominio violada o datos de entrada inválidos."""


class ConsentimientoRequeridoError(DomainException):
    """Operación requiere consentimiento informado explícito."""


class EvaluacionNoEncontradaError(DomainException):
    """La evaluación solicitada no existe en el repositorio."""


class EvaluacionExpiradaError(DomainException):
    """La evaluación temporal ha superado su TTL de 24 horas."""


class EvaluacionYaVinculadaError(DomainException):
    """La evaluación ya fue vinculada a un usuario — operación idempotente rechazada."""


class ModeloNoDisponibleError(DomainException):
    """El modelo ML no pudo cargarse. Fallo crítico — no debe silenciarse."""
