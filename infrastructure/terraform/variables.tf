variable "project_id" {
  type        = string
  description = "Google Cloud Project ID"
}

variable "region" {
  type        = string
  default     = "europe-west1"
  description = "GCP region — europe-west1 para GDPR compliance"
}

variable "env" {
  type        = string
  default     = "production"
  validation {
    condition     = contains(["staging", "production"], var.env)
    error_message = "env debe ser 'staging' o 'production'"
  }
}

variable "app_image" {
  type        = string
  description = "Docker image URL en GCR (gcr.io/project/prevencion-api:sha)"
}
