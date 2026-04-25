# =============================================================================
# PrevencionApp — Terraform: Infraestructura GCP Completa
# Región primaria: europe-west1 (Bélgica) — GDPR compliance
# =============================================================================

terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  backend "gcs" {
    bucket = "prevencion-terraform-state"
    prefix = "prod"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ── Variables ─────────────────────────────────────────────────────────────────
variable "project_id" { type = string }
variable "region"     { default = "europe-west1" }
variable "env"        { default = "production" }
variable "app_image"  { type = string }

# ── Cloud Run — Backend API ───────────────────────────────────────────────────
resource "google_cloud_run_v2_service" "api" {
  name     = "prevencion-api-${var.env}"
  location = var.region

  template {
    service_account = google_service_account.cloud_run_sa.email

    scaling {
      min_instance_count = var.env == "production" ? 1 : 0
      max_instance_count = 10
    }

    containers {
      image = var.app_image

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = false  # CPU always-on en prod
        startup_cpu_boost = true
      }

      env {
        name  = "APP_ENV"
        value = var.env
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }

      # Secretos desde Secret Manager
      env {
        name = "SUPABASE_SERVICE_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.supabase_service_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "SUPABASE_JWT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.supabase_jwt_secret.secret_id
            version = "latest"
          }
        }
      }

      ports { container_port = 8080 }

      startup_probe {
        http_get { path = "/health" }
        initial_delay_seconds = 5
        period_seconds        = 5
        failure_threshold     = 10
      }

      liveness_probe {
        http_get { path = "/health" }
        period_seconds    = 30
        failure_threshold = 3
      }
    }

    timeout = "30s"
    max_instance_request_concurrency = 80
  }
}

# ── Cloud Run — Acceso público ────────────────────────────────────────────────
resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ── Secret Manager ────────────────────────────────────────────────────────────
resource "google_secret_manager_secret" "supabase_service_key" {
  secret_id = "supabase-service-key"
  replication { auto {} }
}

resource "google_secret_manager_secret" "supabase_jwt_secret" {
  secret_id = "supabase-jwt-secret"
  replication { auto {} }
}

resource "google_secret_manager_secret" "sha256_salt" {
  secret_id = "sha256-sal-v1"
  replication { auto {} }
}

# ── GCS Bucket — Modelos ML ───────────────────────────────────────────────────
resource "google_storage_bucket" "models" {
  name          = "${var.project_id}-prevencion-models"
  location      = var.region
  force_destroy = false

  versioning { enabled = true }

  lifecycle_rule {
    condition { age = 90 }
    action    { type = "Delete" }
  }

  uniform_bucket_level_access = true
}

# ── BigQuery — Data Lakehouse ─────────────────────────────────────────────────
resource "google_bigquery_dataset" "analitica" {
  dataset_id  = "prevencion_analitica"
  location    = var.region
  description = "Dataset analítico de evaluaciones clínicas PrevencionApp"

  default_table_expiration_ms = null  # Datos clínicos sin expiración
}

resource "google_bigquery_table" "evaluaciones" {
  dataset_id = google_bigquery_dataset.analitica.dataset_id
  table_id   = "evaluaciones"

  time_partitioning {
    type  = "DAY"
    field = "fecha_creacion"
  }

  schema = jsonencode([
    { name = "evaluacion_id",     type = "STRING",    mode = "REQUIRED" },
    { name = "fecha_creacion",    type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "nivel_inflamacion", type = "STRING",    mode = "NULLABLE" },
    { name = "probabilidad",      type = "FLOAT64",   mode = "NULLABLE" },
    { name = "confianza",         type = "FLOAT64",   mode = "NULLABLE" },
    { name = "pais_id",           type = "INTEGER",   mode = "NULLABLE" },
    { name = "sexo_id",           type = "INTEGER",   mode = "NULLABLE" },
    { name = "edad_anios",        type = "INTEGER",   mode = "NULLABLE" },
    { name = "dolor_articular",   type = "BOOLEAN",   mode = "NULLABLE" },
    { name = "rigidez_matutina",  type = "BOOLEAN",   mode = "NULLABLE" },
    { name = "duracion_rigidez",  type = "INTEGER",   mode = "NULLABLE" },
    { name = "version_cuestionario", type = "STRING", mode = "NULLABLE" },
  ])
}

# ── Cloud Armor — WAF ─────────────────────────────────────────────────────────
resource "google_compute_security_policy" "waf" {
  name        = "prevencion-waf-${var.env}"
  description = "WAF PrevencionApp — OWASP 3.3 + Rate limiting"

  # OWASP Top 10
  rule {
    action   = "deny(403)"
    priority = 1000
    match {
      expr { expression = "evaluatePreconfiguredExpr('xss-v33-stable')" }
    }
    description = "XSS Protection"
  }

  rule {
    action   = "deny(403)"
    priority = 1001
    match {
      expr { expression = "evaluatePreconfiguredExpr('sqli-v33-stable')" }
    }
    description = "SQL Injection Protection"
  }

  # Rate limiting: 10 req/IP/hora para endpoint anónimo
  rule {
    action   = "throttle"
    priority = 2000
    match {
      versioned_expr = "SRC_IPS_V1"
      config { src_ip_ranges = ["*"] }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = 10
        interval_sec = 3600
      }
    }
    description = "Rate limit: 10 evaluaciones/IP/hora"
  }

  # Permitir el resto
  rule {
    action   = "allow"
    priority = 2147483647
    match {
      versioned_expr = "SRC_IPS_V1"
      config { src_ip_ranges = ["*"] }
    }
    description = "Default allow"
  }
}

# ── Service Account para Cloud Run ───────────────────────────────────────────
resource "google_service_account" "cloud_run_sa" {
  account_id   = "prevencion-api-sa"
  display_name = "PrevencionApp API Service Account"
}

resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_storage_bucket_iam_member" "models_reader" {
  bucket = google_storage_bucket.models.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# ── Outputs ───────────────────────────────────────────────────────────────────
output "api_url" {
  value       = google_cloud_run_v2_service.api.uri
  description = "URL de la API de PrevencionApp"
}

output "models_bucket" {
  value = google_storage_bucket.models.url
}
