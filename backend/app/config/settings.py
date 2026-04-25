"""
PrevencionApp — Configuración centralizada con Pydantic BaseSettings.
Las variables de entorno sobreescriben los valores por defecto.
En producción, los secretos se inyectan desde GCP Secret Manager.
"""
from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Entorno ──────────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    debug: bool = False

    # ── Supabase ──────────────────────────────────────────────────────────────
    supabase_url: AnyHttpUrl = Field(..., description="URL del proyecto Supabase")
    supabase_anon_key: str = Field(..., description="Clave anónima pública")
    supabase_service_key: str = Field(..., description="Clave service_role (Secret Manager en prod)")
    supabase_jwt_secret: str = Field(..., description="Secreto JWT de Supabase")

    # ── GCP ───────────────────────────────────────────────────────────────────
    gcp_project_id: str = Field(default="prevencion-app-dev")
    gcp_region: str = Field(default="europe-west1")
    secret_manager_sal_name: str = Field(default="sha256-sal-v1")
    gcs_bucket_models: str = Field(default="prevencion-models-dev")

    # ── ML ────────────────────────────────────────────────────────────────────
    ml_model_path: str = Field(default="./models/model.pkl")
    ml_service_url: str = Field(default="http://localhost:8001")
    ml_confidence_threshold: float = Field(default=0.70, ge=0.0, le=1.0)

    # ── API ───────────────────────────────────────────────────────────────────
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
    )
    api_v1_prefix: str = "/api/v1"
    request_timeout_seconds: int = 30
    rate_limit_per_hour: int = 10  # evaluaciones anónimas por IP/hora

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def supabase_url_str(self) -> str:
        return str(self.supabase_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton de configuración — se carga una sola vez."""
    return Settings()  # type: ignore[call-arg]
