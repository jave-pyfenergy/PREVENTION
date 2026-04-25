# PrevencionApp 🏥

**Plataforma de telemedicina preventiva para detección temprana de inflamación sinovial**

[![CI/CD](https://github.com/org/prevencion-app/actions/workflows/deploy.yml/badge.svg)](https://github.com/org/prevencion-app/actions)
[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-green)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.x-61dafb)](https://react.dev)
[![License](https://img.shields.io/badge/License-Proprietary-red)]()

---

## ✨ Descripción

PrevencionApp es una plataforma de telemedicina preventiva especializada en la detección temprana de inflamación sinovial asociada a patologías reumatológicas. El sistema permite a pacientes:

1. Completar un **formulario clínico estandarizado** (síntomas, localización, duración)
2. Subir **fotografías de sus manos** (con strip automático de metadatos EXIF)
3. Recibir en tiempo real un **análisis de riesgo** generado por modelos de ML
4. Visualizar **mapas de calor Grad-CAM** para validación médica

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                    Browser / App                                 │
│              React + Vite + Supabase JS                         │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTPS (TLS 1.3)
┌──────────────────────▼──────────────────────────────────────────┐
│              Cloud Armor (WAF) + Load Balancer                  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│              Cloud Run — FastAPI (Hexagonal Architecture)        │
│  ┌─────────┐  ┌─────────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ Domain  │  │ Application │  │  Infra   │  │ Entrypoints │  │
│  │Entities │  │ Use Cases   │  │ Adapters │  │  FastAPI    │  │
│  │Services │  │ DTOs, Ports │  │ Supabase │  │  Routes     │  │
│  └─────────┘  └─────────────┘  └──────────┘  └─────────────┘  │
└──────────┬───────────────┬───────────────────────────────────────┘
           │               │
┌──────────▼──┐   ┌────────▼─────────────────────────────────────┐
│  Supabase   │   │              GCP Services                     │
│ PostgreSQL  │   │  Secret Manager · GCS · BigQuery · Functions  │
│   Storage   │   └──────────────────────────────────────────────┘
│     Auth    │
└─────────────┘
```

**Patrón:** Arquitectura Hexagonal (Ports & Adapters)  
**Cloud:** Google Cloud Platform (europe-west1 — GDPR)  
**DB:** Supabase PostgreSQL con RLS + JSONB  
**ML:** scikit-learn/XGBoost (tabular) + CNN ResNet-50 (visual) + Grad-CAM

---

## 🚀 Quick Start (Desarrollo Local)

### Prerrequisitos
- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- Cuenta Supabase (gratis en supabase.com)

### 1. Clonar y configurar
```bash
git clone https://github.com/org/prevencion-app.git
cd PrevencionApp

# Copiar variables de entorno
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
# Editar ambos archivos con tus credenciales de Supabase
```

### 2. Inicializar base de datos
```bash
# En Supabase SQL Editor, ejecutar:
# infrastructure/sql/migrations/001_initial_schema.sql
```

### 3. Levantar con Docker Compose
```bash
docker-compose up --build
```

O por separado:

```bash
# Backend
cd backend
pip install -e ".[dev]"
uvicorn app.entrypoints.api.main:app --reload --port 8080

# Frontend
cd frontend
npm install
npm run dev
```

**URLs:**
- Frontend: http://localhost:5173
- API: http://localhost:8080
- Swagger UI: http://localhost:8080/docs (solo en development)

---

## 🧪 Tests

```bash
cd backend
# Unit tests (sin dependencias externas)
pytest tests/unit/ -v

# Con cobertura
pytest tests/unit/ --cov=app --cov-report=html

# Lint + type check
ruff check app/
mypy app/
```

---

## 📁 Estructura del Proyecto

```
PrevencionApp/
├── backend/                    # FastAPI — Arquitectura Hexagonal
│   ├── app/
│   │   ├── domain/             # Entidades, Value Objects, Servicios
│   │   ├── application/        # Casos de Uso, DTOs, Puertos
│   │   ├── infrastructure/     # Adaptadores: DB, ML, Storage, Hashing
│   │   ├── entrypoints/        # FastAPI: routes, dependencies, main
│   │   └── config/             # Settings (Pydantic), DI Container
│   ├── tests/
│   │   ├── unit/               # Tests de dominio y use cases (mocks)
│   │   ├── integration/        # Tests con Supabase local
│   │   └── e2e/                # Tests de API con httpx TestClient
│   ├── models/                 # Artefactos ML (.pkl, .tflite) — dev
│   └── Dockerfile
├── frontend/                   # React + Vite
│   └── src/
│       ├── hooks/              # useAuth, useEvaluacion, useImageUpload
│       ├── pages/              # Home, Formulario, Resultado, Dashboard
│       ├── stores/             # Zustand: authStore
│       └── lib/                # supabase.js, api.js, exif.js
├── infrastructure/
│   ├── terraform/              # IaC: Cloud Run, WAF, GCS, BigQuery
│   ├── sql/migrations/         # Esquema PostgreSQL + RLS + triggers
│   └── github-actions/         # CI/CD pipeline (4 stages)
└── docker-compose.yml
```

---

## 🔒 Seguridad y Privacidad

| Capa | Implementación |
|------|---------------|
| **PII hashing** | SHA-256 HMAC + sal dinámica (GCP Secret Manager) |
| **EXIF stripping** | piexifjs en frontend antes del upload |
| **RLS** | Row Level Security en todas las tablas de usuario |
| **WAF** | Cloud Armor OWASP 3.3 + rate limiting (10 req/IP/hora) |
| **TLS** | 1.3 end-to-end, terminación en Load Balancer |
| **Consentimiento** | Campo NOT NULL en DB — sin consentimiento no hay procesamiento |
| **Borrado** | GDPR Art. 17 implementado via DELETE policies RLS |

---

## 📊 SLOs

| Métrica | Objetivo |
|---------|---------|
| Uptime API | 99.9% mensual |
| Latencia p95 evaluación | < 500ms |
| Latencia p95 CNN | < 2000ms |
| Error rate 5xx | < 0.1% |
| Precisión modelo ML | > 85% accuracy |

---

## 🗺️ Roadmap

| Fase | Semanas | Objetivo |
|------|---------|---------|
| **MVP Core** | 1–6 | Sistema funcional end-to-end en staging |
| **MVP Clínico** | 7–10 | Modelo ML real + producción con canary |
| **Escalado** | 11–20 | BigQuery ETL, FHIR, federated learning, i18n |

---

## 🤝 Compliance

- **GDPR** (Europa) — datos en europe-west1, consentimiento explícito, derecho al olvido
- **Ley 1581** (Colombia) — tratamiento de datos personales de salud
- **HIPAA-ready** — arquitectura preparada para certificación en EEUU

---

## 📝 Licencia

Propietario — PrevencionApp © 2026. Todos los derechos reservados.

> ⚠️ **Disclaimer médico:** PrevencionApp es una herramienta de apoyo diagnóstico orientativa. No reemplaza la consulta médica profesional. Siempre consulte a un reumatólogo certificado.
