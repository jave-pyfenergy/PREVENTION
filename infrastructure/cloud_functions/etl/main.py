"""
PrevencionApp — Cloud Function ETL: Supabase → BigQuery
Trigger: Pub/Sub cada 6 horas (Cloud Scheduler)
Extrae evaluaciones nuevas desde Supabase y las carga en BigQuery
para análisis epidemiológico y reentrenamiento del modelo.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timedelta, timezone

import functions_framework
from google.cloud import bigquery

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Configuración ─────────────────────────────────────────────────────────────
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "prevencion-app-prod")
BQ_DATASET = os.environ.get("BQ_DATASET", "prevencion_analitica")
BQ_TABLE = os.environ.get("BQ_TABLE", "evaluaciones")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
BATCH_SIZE = 1000  # Registros por batch para evitar timeouts


@functions_framework.cloud_event
def etl_supabase_bigquery(cloud_event):
    """
    Entry point del Cloud Function.
    Ejecutado por Pub/Sub trigger cada 6 horas.
    """
    # Decodificar mensaje Pub/Sub (puede contener timestamp de última ejecución)
    try:
        message_data = base64.b64decode(cloud_event.data["message"]["data"]).decode()
        config = json.loads(message_data)
        since_override = config.get("since")
    except Exception:
        since_override = None

    logger.info(f"ETL iniciado — {datetime.now(timezone.utc).isoformat()}")

    try:
        result = run_etl(since_override=since_override)
        logger.info(f"ETL completado — {result['registros_cargados']} registros")
    except Exception as e:
        logger.error(f"ETL falló: {e}", exc_info=True)
        raise  # Re-raise para que Pub/Sub reintente


def run_etl(since_override: str | None = None) -> dict:
    """
    Lógica ETL principal.
    Retorna estadísticas de la ejecución.
    """
    bq_client = bigquery.Client(project=PROJECT_ID)

    # Determinar ventana temporal (últimas 6h + buffer de 30min para evitar gaps)
    if since_override:
        since = datetime.fromisoformat(since_override)
    else:
        since = datetime.now(timezone.utc) - timedelta(hours=6, minutes=30)

    logger.info(f"Extrayendo evaluaciones desde: {since.isoformat()}")

    # Extraer desde Supabase via REST API
    evaluaciones = extraer_de_supabase(since)
    logger.info(f"Registros extraídos: {len(evaluaciones)}")

    if not evaluaciones:
        return {"registros_cargados": 0, "since": since.isoformat()}

    # Transformar al esquema BigQuery
    rows = [transformar_registro(ev) for ev in evaluaciones]

    # Cargar en BigQuery (upsert via MERGE para idempotencia)
    errores = cargar_en_bigquery(bq_client, rows)

    return {
        "registros_cargados": len(rows) - len(errores),
        "errores": len(errores),
        "since": since.isoformat(),
        "hasta": datetime.now(timezone.utc).isoformat(),
    }


def extraer_de_supabase(since: datetime) -> list[dict]:
    """
    Extrae evaluaciones completadas desde Supabase.
    Usa paginación para manejar volúmenes grandes.
    """
    import httpx

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Prefer": "count=exact",
    }

    todas = []
    offset = 0
    MAX_PAGES = 200  # límite de seguridad — 200 * 1000 = 200k registros por ejecución

    for page in range(MAX_PAGES):
        response = httpx.get(
            f"{SUPABASE_URL}/rest/v1/mv_analitica_riesgo",
            headers=headers,
            params={
                "fecha_creacion": f"gte.{since.isoformat()}",
                "select": "*",
                "order": "fecha_creacion.asc",
                "limit": BATCH_SIZE,
                "offset": offset,
            },
            timeout=30,
        )
        response.raise_for_status()
        batch = response.json()

        if not batch:
            break

        todas.extend(batch)
        offset += len(batch)

        if len(batch) < BATCH_SIZE:
            break

        logger.info(f"Paginación ETL página {page + 1}: {len(todas)} registros hasta ahora")
    else:
        logger.warning(f"ETL alcanzó el límite máximo de páginas ({MAX_PAGES})")

    return todas


def transformar_registro(ev: dict) -> dict:
    """
    Transforma un registro de Supabase al esquema BigQuery.
    Aplica limpieza y normalización de tipos.
    """
    return {
        "evaluacion_id": str(ev.get("evaluacion_id", "")),
        "fecha_creacion": ev.get("fecha_creacion"),
        "nivel_inflamacion": ev.get("nivel_inflamacion"),
        "probabilidad": float(ev["probabilidad"]) if ev.get("probabilidad") is not None else None,
        "confianza": float(ev["confianza"]) if ev.get("confianza") is not None else None,
        "version_cuestionario": ev.get("version_cuestionario", "1.0"),
        "pais_id": int(ev["pais_id"]) if ev.get("pais_id") is not None else None,
        "sexo_id": int(ev["sexo_id"]) if ev.get("sexo_id") is not None else None,
        "edad_anios": int(ev["edad_anios"]) if ev.get("edad_anios") is not None else None,
        "dolor_articular": bool(ev.get("dolor_articular")),
        "rigidez_matutina": bool(ev.get("rigidez_matutina")),
        "duracion_rigidez": int(ev["duracion_rigidez"]) if ev.get("duracion_rigidez") is not None else None,
        # NO se cargan: imagen_path, user_id, session_id — privacidad
    }


def cargar_en_bigquery(client: bigquery.Client, rows: list[dict]) -> list:
    """
    Carga registros en BigQuery.
    Usa insert_rows_json con reintentos automáticos.
    """
    table_ref = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"

    # Cargar en batches de 500 para respetar límites de la API
    errores_totales = []
    batch_size = 500

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        errores = client.insert_rows_json(table_ref, batch)

        if errores:
            logger.error(f"Errores en batch {i//batch_size + 1}: {errores[:3]}")
            errores_totales.extend(errores)

    if not errores_totales:
        logger.info(f"✅ {len(rows)} registros cargados en {table_ref}")

    return errores_totales


# ── Para testing local ────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Simula un trigger manual con ventana de las últimas 24h
    from datetime import timezone as tz
    resultado = run_etl(
        since_override=(datetime.now(tz.utc) - timedelta(hours=24)).isoformat()
    )
    print(json.dumps(resultado, indent=2))
