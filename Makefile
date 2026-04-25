.PHONY: help dev test lint build train-model

help:
	@echo "PrevencionApp — Comandos disponibles"
	@echo "======================================"
	@echo "  make dev          — Levantar en desarrollo (Docker Compose)"
	@echo "  make test         — Ejecutar todos los tests"
	@echo "  make lint         — Lint + type check backend"
	@echo "  make build        — Build imagen Docker de producción"
	@echo "  make train-model  — Entrenar modelo ML dummy"
	@echo "  make migrate      — Aplicar migraciones SQL"
	@echo "  make clean        — Limpiar artefactos de build"

dev:
	docker-compose up --build

dev-backend:
	cd backend && uvicorn app.entrypoints.api.main:app --reload --port 8080

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && pytest tests/ -v --tb=short

test-unit:
	cd backend && pytest tests/unit/ -v

test-integration:
	cd backend && pytest tests/integration/ -v

test-e2e:
	cd backend && pytest tests/e2e/ -v

test-cov:
	cd backend && pytest tests/ --cov=app --cov-report=html --cov-report=term-missing

lint:
	cd backend && ruff check app/ tests/ && mypy app/ --ignore-missing-imports

format:
	cd backend && ruff format app/ tests/

build:
	docker build -t prevencion-api:latest ./backend --target runtime

train-model:
	python scripts/train_dummy_model.py

migrate:
	@echo "Ejecutar manualmente en Supabase SQL Editor:"
	@echo "  infrastructure/sql/migrations/001_initial_schema.sql"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
	rm -rf backend/.pytest_cache backend/.mypy_cache backend/htmlcov
	rm -rf frontend/dist frontend/node_modules/.vite
