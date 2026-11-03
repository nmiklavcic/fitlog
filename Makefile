# Local development helpers. Servers are provisioned with Vagrant / cloud-init instead;
# see docs/deploy/DEPLOY-NOTES.md for the production steps.
SHELL := /bin/bash
VENV := backend/.venv
# Run manage.py from backend/ with the dev-only environment loaded.
MANAGE := cd backend && set -a && . ./dev.env && set +a && .venv/bin/python manage.py

.DEFAULT_GOAL := help
.PHONY: help services services-stop services-apt setup migrate seed-exercises superuser \
        backend frontend build check-deploy shell

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

services: ## Start PostgreSQL 16 + Redis 7 in Docker (laptop only)
	docker run -d --name liftlog-postgres -p 5432:5432 \
	  -e POSTGRES_USER=liftlog -e POSTGRES_PASSWORD=liftlog -e POSTGRES_DB=liftlog \
	  postgres:16 2>/dev/null || docker start liftlog-postgres
	docker run -d --name liftlog-redis -p 6379:6379 redis:7 2>/dev/null || docker start liftlog-redis

services-stop: ## Stop the Docker dev services
	docker stop liftlog-postgres liftlog-redis

services-apt: ## Alternative to Docker: install PostgreSQL + Redis with apt and create the dev DB
	sudo apt-get install -y postgresql redis-server
	sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='liftlog'" | grep -q 1 || \
	  sudo -u postgres psql -c "CREATE ROLE liftlog LOGIN PASSWORD 'liftlog'"
	sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='liftlog'" | grep -q 1 || \
	  sudo -u postgres createdb -O liftlog liftlog

setup: ## Create the Python venv and install backend + frontend dependencies
	test -d $(VENV) || python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r backend/requirements.txt
	cd frontend && npm ci

migrate: ## Apply database migrations
	$(MANAGE) migrate

seed-exercises: ## Load the bundled exercise catalogue (safe to re-run)
	$(MANAGE) load_exercises

superuser: ## Create a Django admin superuser
	$(MANAGE) createsuperuser

backend: ## Run the Django dev server on :8000
	$(MANAGE) runserver 127.0.0.1:8000

frontend: ## Run the Vite dev server on :5173 (proxies /api and /media to :8000)
	cd frontend && npm run dev

build: ## Build the production frontend into frontend/dist
	cd frontend && npm run build

check-deploy: ## Run Django's deployment checklist with production-like settings
	cd backend && DJANGO_DEBUG=0 DJANGO_SECRET_KEY=$$(python3 -c 'import secrets;print(secrets.token_urlsafe(50))') \
	  MEDIA_URL_SIGNING_SECRET=x DJANGO_ALLOWED_HOSTS=example.com .venv/bin/python manage.py check --deploy

shell: ## Django shell
	$(MANAGE) shell
