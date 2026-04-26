"""
PrevencionApp — Adaptador Supabase Storage.
Todas las llamadas al SDK síncrono se delegan a run_in_executor para
no bloquear el event loop de asyncio.
"""
from __future__ import annotations

import asyncio
import logging
from functools import partial
from uuid import UUID

from supabase import Client, create_client

from app.application.ports.ports import StoragePort

logger = logging.getLogger(__name__)

BUCKET_TEMP = "temp_images"
BUCKET_PERMANENT = "permanent_images"


class SupabaseStorageAdapter(StoragePort):
    def __init__(self, url: str, service_key: str) -> None:
        self._client: Client = create_client(url, service_key)

    async def _run(self, fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    async def generar_signed_url_subida(
        self, bucket: str, path: str, ttl_seconds: int = 300
    ) -> str:
        result = await self._run(
            lambda: self._client.storage.from_(bucket).create_signed_upload_url(path)
        )
        return result["signedUrl"]

    async def mover_imagen_a_permanente(self, path_temp: str, user_id: UUID) -> str:
        filename = path_temp.split("/")[-1]
        dest_path = f"{user_id}/{filename}"
        await self._run(
            lambda: self._client.storage.from_(BUCKET_PERMANENT).copy(path_temp, dest_path)
        )
        await self.eliminar_imagen(BUCKET_TEMP, path_temp)
        logger.info("Imagen movida a permanente: %s", dest_path)
        return dest_path

    async def eliminar_imagen(self, bucket: str, path: str) -> None:
        try:
            await self._run(
                lambda: self._client.storage.from_(bucket).remove([path])
            )
        except Exception as e:
            logger.warning("No se pudo eliminar %s/%s: %s", bucket, path, e)
