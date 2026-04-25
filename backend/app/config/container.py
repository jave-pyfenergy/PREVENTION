"""
PrevencionApp — Contenedor de Inyección de Dependencias.
Patrón manual explícito (sin frameworks) — simple, testeable, sin magia.
"""
from functools import lru_cache

from app.application.ports.hasher_port import HasherPort
from app.application.ports.ml_model_port import MLModelPort
from app.application.ports.repositorio_port import RepositorioPort
from app.application.ports.storage_port import StoragePort
from app.application.use_cases.obtener_historial import ObtenerHistorial
from app.application.use_cases.predecir_inflamacion import PredecirInflamacion
from app.application.use_cases.registrar_paciente import RegistrarPaciente
from app.application.use_cases.vincular_evaluacion import VincularEvaluacion
from app.config.settings import Settings, get_settings
from app.infrastructure.db.supabase_adapter import SupabaseAdapter
from app.infrastructure.hashing.sha256_adapter import SHA256Adapter
from app.infrastructure.ml.sklearn_adapter import SklearnAdapter
from app.infrastructure.storage.supabase_storage_adapter import SupabaseStorageAdapter


class Container:
    """
    Contenedor DI. Se instancia una vez al arrancar la aplicación.
    Los adaptadores se construyen en orden de dependencias.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._init_adapters()
        self._init_use_cases()

    def _init_adapters(self) -> None:
        # Infraestructura base
        self._repositorio: RepositorioPort = SupabaseAdapter(
            url=self._settings.supabase_url_str,
            service_key=self._settings.supabase_service_key,
        )
        self._storage: StoragePort = SupabaseStorageAdapter(
            url=self._settings.supabase_url_str,
            service_key=self._settings.supabase_service_key,
        )
        self._hasher: HasherPort = SHA256Adapter(
            project_id=self._settings.gcp_project_id,
            secret_name=self._settings.secret_manager_sal_name,
            app_env=self._settings.app_env,
        )
        self._ml_model: MLModelPort = SklearnAdapter(
            model_path=self._settings.ml_model_path,
            confidence_threshold=self._settings.ml_confidence_threshold,
        )

    def _init_use_cases(self) -> None:
        self._predecir = PredecirInflamacion(
            ml_model=self._ml_model,
            repositorio=self._repositorio,
            hasher=self._hasher,
            storage=self._storage,
        )
        self._vincular = VincularEvaluacion(
            repositorio=self._repositorio,
            storage=self._storage,
        )
        self._obtener_historial = ObtenerHistorial(repositorio=self._repositorio)
        self._registrar_paciente = RegistrarPaciente(
            repositorio=self._repositorio,
            hasher=self._hasher,
        )

    # ── Getters públicos ──────────────────────────────────────────────────────

    @property
    def predecir_inflamacion(self) -> PredecirInflamacion:
        return self._predecir

    @property
    def vincular_evaluacion(self) -> VincularEvaluacion:
        return self._vincular

    @property
    def obtener_historial(self) -> ObtenerHistorial:
        return self._obtener_historial

    @property
    def registrar_paciente(self) -> RegistrarPaciente:
        return self._registrar_paciente

    @property
    def repositorio(self) -> RepositorioPort:
        return self._repositorio

    @property
    def storage(self) -> StoragePort:
        return self._storage


@lru_cache(maxsize=1)
def get_container() -> Container:
    """Singleton del contenedor — una sola instancia por proceso."""
    return Container(settings=get_settings())
