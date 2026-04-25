"""
PrevencionApp — Adaptador Supabase Storage.
Gestión de imágenes médicas con Signed URLs y política de privacidad.
"""
from __future__ import annotations

import logging
from uuid import UUID

from supabase import Client, create_client

from app.application.ports.ports import StoragePort

logger = logging.getLogger(__name__)

BUCKET_TEMP = "temp_images"
BUCKET_PERMANENT = "permanent_images"


class SupabaseStorageAdapter(StoragePort):
    def __init__(self, url: str, service_key: str) -> None:
        self._client: Client = create_client(url, service_key)

    async def generar_signed_url_subida(
        self, bucket: str, path: str, ttl_seconds: int = 300
    ) -> str:
        """
        Genera URL firmada para upload directo al bucket.
        El cliente sube directamente a Supabase — el tráfico NO pasa por FastAPI.
        """
        try:
            result = self._client.storage.from_(bucket).create_signed_upload_url(path)
            return result["signedUrl"]
        except Exception as e:
            logger.error(f"Error generando Signed URL para {bucket}/{path}", exc_info=e)
            raise

    async def mover_imagen_a_permanente(
        self, path_temp: str, user_id: UUID
    ) -> str:
        """
        Copia imagen de temp_images a permanent_images/{user_id}/filename.
        Elimina la copia temporal después de la copia exitosa.
        """
        filename = path_temp.split("/")[-1]
        dest_path = f"{user_id}/{filename}"

        try:
            # Supabase SDK: copy entre buckets
            self._client.storage.from_(BUCKET_PERMANENT).copy(
                path_temp, dest_path
            )
            # Eliminar temporal
            await self.eliminar_imagen(BUCKET_TEMP, path_temp)
            logger.info(f"Imagen movida a permanente: {dest_path}")
            return dest_path
        except Exception as e:
            logger.error("Error moviendo imagen a permanente", exc_info=e)
            raise

    async def eliminar_imagen(self, bucket: str, path: str) -> None:
        try:
            self._client.storage.from_(bucket).remove([path])
        except Exception as e:
            logger.warning(f"No se pudo eliminar {bucket}/{path}", exc_info=e)
