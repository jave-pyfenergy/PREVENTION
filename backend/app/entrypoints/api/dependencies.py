"""
PrevencionApp — Dependencias de FastAPI.
Validación JWT, extracción de user_id y resolución de use cases.
"""

from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, status

from app.application.use_cases.obtener_historial import ObtenerHistorial
from app.application.use_cases.predecir_inflamacion import PredecirInflamacion
from app.application.use_cases.registrar_paciente import RegistrarPaciente
from app.application.use_cases.vincular_evaluacion import VincularEvaluacion
from app.config.container import Container, get_container
from app.config.settings import Settings, get_settings
from app.infrastructure.storage.supabase_storage_adapter import SupabaseStorageAdapter


def get_predecir_use_case(
    container: Annotated[Container, Depends(get_container)],
) -> PredecirInflamacion:
    return container.predecir_inflamacion


def get_vincular_use_case(
    container: Annotated[Container, Depends(get_container)],
) -> VincularEvaluacion:
    return container.vincular_evaluacion


def get_historial_use_case(
    container: Annotated[Container, Depends(get_container)],
) -> ObtenerHistorial:
    return container.obtener_historial


def get_registrar_use_case(
    container: Annotated[Container, Depends(get_container)],
) -> RegistrarPaciente:
    return container.registrar_paciente


def get_storage(
    container: Annotated[Container, Depends(get_container)],
) -> SupabaseStorageAdapter:
    return container.storage  # type: ignore[return-value]


def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> UUID:
    """
    Extrae y valida el JWT de Supabase Auth.
    Retorna el user_id (sub) del payload.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticación requerido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise ValueError("Token sin sub (user_id)")
        return UUID(user_id_str)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
        )
    except (jwt.InvalidTokenError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {e}",
        )


# Type aliases para inyección limpia en routes
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]
PredecirDep = Annotated[PredecirInflamacion, Depends(get_predecir_use_case)]
VincularDep = Annotated[VincularEvaluacion, Depends(get_vincular_use_case)]
HistorialDep = Annotated[ObtenerHistorial, Depends(get_historial_use_case)]
RegistrarDep = Annotated[RegistrarPaciente, Depends(get_registrar_use_case)]
