"""
Instancia singleton del rate limiter — compartida entre main.py y routes.
Usa Redis como backend cuando está disponible para compartir contadores
entre múltiples workers de gunicorn (evita bypass por worker).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config.settings import get_settings

_settings = get_settings()

# Redis disponible → contadores compartidos entre todos los workers/instancias.
# Sin Redis → memoria local (solo válido en desarrollo con 1 worker).
_storage_uri = _settings.redis_url or "memory://"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage_uri,
)
