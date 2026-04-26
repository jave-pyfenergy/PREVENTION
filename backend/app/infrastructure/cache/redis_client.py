"""
PrevencionApp — Cliente Redis.
Provee un cliente async con fallback graceful cuando Redis no está disponible.
Usado para: cache de resultados, rate limiting compartido, estado DriftDetector.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    logger.warning("redis no instalado — cache y rate limiting funcionarán solo en memoria")


class RedisClient:
    """
    Wrapper sobre redis.asyncio con degradación graceful.
    Si Redis no está configurado o no responde, todas las operaciones
    retornan None / False sin propagar excepciones.
    """

    def __init__(self, url: str | None = None) -> None:
        self._url = url
        self._client: Optional["aioredis.Redis"] = None  # type: ignore[name-defined]
        self._available = bool(url and _REDIS_AVAILABLE)

    async def connect(self) -> None:
        if not self._available:
            return
        try:
            self._client = aioredis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=1,
            )
            await self._client.ping()
            logger.info("Redis conectado: %s", self._url)
        except Exception as e:
            logger.warning("Redis no disponible, operando sin cache: %s", e)
            self._client = None
            self._available = False

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    async def get(self, key: str) -> str | None:
        if not self._client:
            return None
        try:
            return await self._client.get(key)
        except Exception as e:
            logger.debug("Redis GET error: %s", e)
            return None

    async def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        if not self._client:
            return
        try:
            await self._client.setex(key, ttl_seconds, value)
        except Exception as e:
            logger.debug("Redis SETEX error: %s", e)

    async def delete(self, key: str) -> None:
        if not self._client:
            return
        try:
            await self._client.delete(key)
        except Exception as e:
            logger.debug("Redis DEL error: %s", e)

    async def hset(self, name: str, mapping: dict) -> None:
        if not self._client:
            return
        try:
            await self._client.hset(name, mapping=mapping)
        except Exception as e:
            logger.debug("Redis HSET error: %s", e)

    async def hgetall(self, name: str) -> dict:
        if not self._client:
            return {}
        try:
            return await self._client.hgetall(name) or {}
        except Exception as e:
            logger.debug("Redis HGETALL error: %s", e)
            return {}

    @property
    def is_available(self) -> bool:
        return self._available and self._client is not None
