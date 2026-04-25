"""
PrevencionApp — Adaptador de Hashing SHA-256.
Usa sal dinámica almacenada en GCP Secret Manager.
En desarrollo/test, usa sal local configurable.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Literal

from app.application.ports.ports import HasherPort

logger = logging.getLogger(__name__)

# Sal de fallback SOLO para entornos no productivos
_DEV_SALT = "DEV_SALT_DO_NOT_USE_IN_PRODUCTION_32B"


class SHA256Adapter(HasherPort):
    """
    Implementa hashing SHA-256 con sal dinámica.

    En producción: la sal se obtiene de GCP Secret Manager (una sola vez, cacheada).
    En desarrollo: usa _DEV_SALT para facilitar tests locales.
    """

    def __init__(
        self,
        project_id: str,
        secret_name: str,
        app_env: Literal["development", "staging", "production"] = "development",
    ) -> None:
        self._project_id = project_id
        self._secret_name = secret_name
        self._app_env = app_env
        self._sal: bytes | None = None

    async def _obtener_sal(self) -> bytes:
        """Obtiene la sal una sola vez y la cachea en memoria."""
        if self._sal is not None:
            return self._sal

        if self._app_env != "production":
            logger.warning("Usando sal de desarrollo — NO USAR EN PRODUCCIÓN")
            self._sal = _DEV_SALT.encode("utf-8")
            return self._sal

        try:
            from google.cloud import secretmanager

            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{self._project_id}/secrets/{self._secret_name}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            self._sal = response.payload.data
            logger.info("Sal SHA-256 cargada desde Secret Manager")
        except Exception as e:
            logger.critical(
                "No se pudo obtener sal desde Secret Manager — ABORTING", exc_info=e
            )
            raise RuntimeError("No se pudo obtener sal de hashing segura") from e

        return self._sal

    async def hashear(self, valor: str) -> str:
        """
        Retorna el hash hex SHA-256 HMAC del valor con la sal.
        Usa HMAC-SHA256 (más seguro que SHA256(sal + valor)).
        """
        sal = await self._obtener_sal()
        digest = hmac.new(sal, valor.encode("utf-8"), hashlib.sha256).hexdigest()
        return digest

    async def verificar(self, valor: str, hash_almacenado: str) -> bool:
        """Verificación en tiempo constante para evitar timing attacks."""
        hash_calculado = await self.hashear(valor)
        return hmac.compare_digest(hash_calculado, hash_almacenado)
