# Agents - LLM Batch Processing Platform
# =====================================
#
# Usage:
#   make help          Show this help message
#   make dev           Start full development environment
#   make test          Run all tests
#   make check         Run all code quality checks
#
# For more details, see README.md

.PHONY: help install install-dev services api frontend dev dev-full stop clean \
        test test-cov test-unit test-integration \
        lint format typecheck check \
        db-migrate db-upgrade db-downgrade db-revision setup-taskq taskq-worker processing-service \
        build docker-build docker-push \
        logs shell check-tasks check-jobs db-shell

# Default target
.DEFAULT_GOAL := help

# Colors for terminal output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Project settings
PYTHON := python3
UV := uv
NPM := npm
DOCKER_COMPOSE := docker-compose

# ============================================================================
# HELP
# ============================================================================

help: ## Show this help message
	@echo ""
	@echo "$(BLUE)Agents - LLM Batch Processing Platform$(NC)"
	@echo "========================================"
	@echo ""
	@echo "$(GREEN)Quick Start:$(NC)"
	@echo "  make install    Install all dependencies"
	@echo "  make dev        Start full development environment"
	@echo "  make test       Run all tests"
	@echo ""
	@echo "$(GREEN)Available targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""

# ============================================================================
# INSTALLATION
# ============================================================================

install: install-python install-frontend ## Install all dependencies
	@echo "$(GREEN)All dependencies installed!$(NC)"

install-python: ## Install Python dependencies
	@echo "$(BLUE)Installing Python dependencies...$(NC)"
	$(UV) pip install -e ".[dev]"

install-frontend: ## Install frontend dependencies
	@echo "$(BLUE)Installing frontend dependencies...$(NC)"
	cd web && $(NPM) install

# ============================================================================
# DEVELOPMENT
# ============================================================================

dev: ## Start full development environment (services + API + frontend)
	@echo "$(BLUE)Starting development environment...$(NC)"
	@make services-up
	@sleep 3
	@make db-upgrade
	@echo "$(GREEN)Starting API and frontend...$(NC)"
	@trap 'make stop' EXIT; \
	$(MAKE) -j2 api-dev frontend-dev

dev-full: ## Start everything (services + API + frontend + worker + processing)
	@echo "$(BLUE)Starting full development environment...$(NC)"
	@make services-up
	@sleep 3
	@make db-upgrade
	@make setup-taskq
	@echo ""
	@echo "$(GREEN)========================================$(NC)"
	@echo "$(GREEN)Starting all services:$(NC)"
	@echo "  - API server:         http://localhost:8002"
	@echo "  - Frontend:           http://localhost:3000"
	@echo "  - Processing Service: http://localhost:8001"
	@echo "  - TaskQ Worker:       polling database"
	@echo "$(GREEN)========================================$(NC)"
	@echo ""
	@trap 'make stop' EXIT; \
	$(MAKE) -j4 api-dev frontend-dev processing-service taskq-worker

dev-api: services-up db-upgrade api-dev ## Start services and API only

dev-frontend: frontend-dev ## Start frontend only (assumes API is running)

services: services-up ## Alias for services-up

services-up: ## Start infrastructure services (PostgreSQL, MinIO, Redis)
	@echo "$(BLUE)Starting infrastructure services...$(NC)"
	$(DOCKER_COMPOSE) up -d postgres minio redis
	@echo "$(GREEN)Services started!$(NC)"
	@echo "  PostgreSQL: localhost:5432"
	@echo "  MinIO:      localhost:9000 (console: 9001)"
	@echo "  Redis:      localhost:6379"

services-down: ## Stop infrastructure services
	@echo "$(BLUE)Stopping infrastructure services...$(NC)"
	$(DOCKER_COMPOSE) down

api: api-dev ## Alias for api-dev

api-dev: ## Start FastAPI backend in development mode
	@echo "$(BLUE)Starting API server on port 8002...$(NC)"
	PORT=8002 RELOAD=true \
		ENCRYPTION_KEY=_S2uN0jJ6A-k0yROjOMoXYMt3jVbhP_jM9HoDCPq8ss= \
		S3_ENDPOINT_URL=http://localhost:9000 \
		AWS_ACCESS_KEY_ID=minioadmin \
		AWS_SECRET_ACCESS_KEY=minioadmin \
		S3_BUCKET_NAME=agents \
		DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/agents \
		$(UV) run agents-api

api-prod: ## Start FastAPI backend in production mode
	@echo "$(BLUE)Starting API server (production)...$(NC)"
	$(UV) run agents-api

frontend: frontend-dev ## Alias for frontend-dev

frontend-dev: ## Start Next.js frontend in development mode
	@echo "$(BLUE)Starting frontend...$(NC)"
	cd web && $(NPM) run dev

frontend-build: ## Build Next.js frontend for production
	@echo "$(BLUE)Building frontend...$(NC)"
	cd web && $(NPM) run build

stop: ## Stop all services
	@echo "$(BLUE)Stopping all services...$(NC)"
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)All services stopped.$(NC)"

clean: stop ## Stop services and clean up generated files
	@echo "$(BLUE)Cleaning up...$(NC)"
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf __pycache__
	rm -rf agents/__pycache__
	rm -rf agents/**/__pycache__
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf dist
	rm -rf *.egg-info
	rm -rf web/.next
	rm -rf web/node_modules/.cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)Cleanup complete.$(NC)"

# ============================================================================
# TESTING
# ============================================================================

test: ## Run all tests
	@echo "$(BLUE)Running tests...$(NC)"
	pytest tests/ -v

test-cov: ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	pytest tests/ -v --cov=agents --cov-report=term-missing --cov-report=html
	@echo "$(GREEN)Coverage report: htmlcov/index.html$(NC)"

test-unit: ## Run unit tests only
	@echo "$(BLUE)Running unit tests...$(NC)"
	pytest tests/ -v -m "not integration"

test-integration: ## Run integration tests (requires services)
	@echo "$(BLUE)Running integration tests...$(NC)"
	pytest tests/ -v -m integration

test-watch: ## Run tests in watch mode
	@echo "$(BLUE)Running tests in watch mode...$(NC)"
	ptw tests/ -- -v

test-frontend: ## Run frontend tests
	@echo "$(BLUE)Running frontend tests...$(NC)"
	cd web && $(NPM) test

# ============================================================================
# CODE QUALITY
# ============================================================================

check: lint typecheck test ## Run all code quality checks and tests
	@echo "$(GREEN)All checks passed!$(NC)"

lint: ## Run linter (ruff)
	@echo "$(BLUE)Running linter...$(NC)"
	ruff check agents/ tests/
	@echo "$(GREEN)Linting passed!$(NC)"

lint-fix: ## Run linter and fix issues
	@echo "$(BLUE)Running linter with fixes...$(NC)"
	ruff check agents/ tests/ --fix
	@echo "$(GREEN)Linting fixes applied!$(NC)"

format: ## Format code (ruff format)
	@echo "$(BLUE)Formatting code...$(NC)"
	ruff format agents/ tests/
	ruff check agents/ tests/ --fix
	@echo "$(GREEN)Formatting complete!$(NC)"

format-check: ## Check code formatting without changes
	@echo "$(BLUE)Checking code formatting...$(NC)"
	ruff format agents/ tests/ --check
	@echo "$(GREEN)Formatting check passed!$(NC)"

typecheck: ## Run type checker (mypy)
	@echo "$(BLUE)Running type checker...$(NC)"
	mypy agents/
	@echo "$(GREEN)Type checking passed!$(NC)"

# ============================================================================
# DATABASE
# ============================================================================

db-upgrade: ## Run database migrations (upgrade to latest)
	@echo "$(BLUE)Running database migrations...$(NC)"
	$(UV) run alembic upgrade head
	@echo "$(GREEN)Migrations complete!$(NC)"

db-downgrade: ## Downgrade database by one revision
	@echo "$(BLUE)Downgrading database...$(NC)"
	$(UV) run alembic downgrade -1

db-revision: ## Create a new migration revision
	@echo "$(BLUE)Creating new migration...$(NC)"
	@read -p "Migration message: " msg; \
	$(UV) run alembic revision --autogenerate -m "$$msg"

db-current: ## Show current database revision
	@echo "$(BLUE)Current database revision:$(NC)"
	$(UV) run alembic current

db-history: ## Show migration history
	@echo "$(BLUE)Migration history:$(NC)"
	$(UV) run alembic history

db-reset: ## Reset database (drop all tables and re-migrate)
	@echo "$(RED)WARNING: This will delete all data!$(NC)"
	@read -p "Are you sure? [y/N] " confirm; \
	if [ "$$confirm" = "y" ]; then \
		$(UV) run alembic downgrade base; \
		$(UV) run alembic upgrade head; \
		echo "$(GREEN)Database reset complete.$(NC)"; \
	else \
		echo "$(YELLOW)Cancelled.$(NC)"; \
	fi

setup-taskq: ## Setup TaskQ tables and llm_processing queue
	@echo "$(BLUE)Setting up TaskQ schema and queue...$(NC)"
	docker exec -i agents-postgres psql -U postgres -d agents < scripts/sql/setup_taskq.sql
	@echo "$(GREEN)TaskQ setup complete!$(NC)"

taskq-worker: ## Start TaskQ LLM worker (connects to agents database)
	@echo "$(BLUE)Starting TaskQ LLM Processing Worker...$(NC)"
	cd ~/Projects/taskqworker && \
		ERL_FLAGS="+Bc" \
		TASKQ_DB_HOST=localhost \
		TASKQ_DB_PORT=5433 \
		TASKQ_DB_NAME=agents \
		TASKQ_DB_USER=postgres \
		TASKQ_DB_PASSWORD=postgres \
		PROCESSING_SERVICE_URL=http://localhost:8001/process \
		gleam run -m taskq/llm_worker

processing-service: ## Start the LLM Processing Service (port 8001)
	@echo "$(BLUE)Starting Processing Service on port 8001...$(NC)"
	RELOAD=true \
		DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/agents \
		S3_ENDPOINT_URL=http://localhost:9000 \
		AWS_ACCESS_KEY_ID=minioadmin \
		AWS_SECRET_ACCESS_KEY=minioadmin \
		S3_BUCKET_NAME=agents \
		ENCRYPTION_KEY=_S2uN0jJ6A-k0yROjOMoXYMt3jVbhP_jM9HoDCPq8ss= \
		$(UV) run python -m agents.processing_service.app

# ============================================================================
# DOCKER
# ============================================================================

docker-build: ## Build Docker images
	@echo "$(BLUE)Building Docker images...$(NC)"
	$(DOCKER_COMPOSE) build

docker-build-api: ## Build API Docker image only
	@echo "$(BLUE)Building API Docker image...$(NC)"
	docker build -t agents-api:latest -f Dockerfile .

docker-push: ## Push Docker images to registry
	@echo "$(BLUE)Pushing Docker images...$(NC)"
	@echo "$(YELLOW)Configure DOCKER_REGISTRY first$(NC)"
	# docker push $(DOCKER_REGISTRY)/agents-api:latest

docker-up: ## Start all services with Docker Compose
	@echo "$(BLUE)Starting all services...$(NC)"
	$(DOCKER_COMPOSE) up -d

docker-down: ## Stop all Docker Compose services
	@echo "$(BLUE)Stopping all services...$(NC)"
	$(DOCKER_COMPOSE) down

docker-logs: ## Show Docker Compose logs
	$(DOCKER_COMPOSE) logs -f

# ============================================================================
# UTILITIES
# ============================================================================

logs: ## Show logs from all services
	$(DOCKER_COMPOSE) logs -f

logs-api: ## Show API logs
	$(DOCKER_COMPOSE) logs -f api

logs-db: ## Show database logs
	$(DOCKER_COMPOSE) logs -f postgres

check-tasks: ## Show TaskQ task statuses
	@echo "$(BLUE)TaskQ Tasks Summary:$(NC)"
	@docker exec -it agents-postgres psql -U postgres -d agents -c \
		"SELECT status, COUNT(*) FROM tasks GROUP BY status ORDER BY status;"
	@echo ""
	@echo "$(BLUE)Recent Tasks:$(NC)"
	@docker exec -it agents-postgres psql -U postgres -d agents -c \
		"SELECT id, status, payload->>'web_job_id' as job_id, attempts, created_at FROM tasks ORDER BY created_at DESC LIMIT 10;"

check-jobs: ## Show WebJob statuses
	@echo "$(BLUE)WebJobs Summary:$(NC)"
	@docker exec -it agents-postgres psql -U postgres -d agents -c \
		"SELECT status, COUNT(*) FROM web_jobs GROUP BY status ORDER BY status;"
	@echo ""
	@echo "$(BLUE)Recent Jobs:$(NC)"
	@docker exec -it agents-postgres psql -U postgres -d agents -c \
		"SELECT id, status, processed_units, failed_units, model, created_at FROM web_jobs ORDER BY created_at DESC LIMIT 10;"

job-errors: ## Show failed jobs with error messages
	@echo "$(BLUE)Failed Jobs with Errors:$(NC)"
	@docker exec -it agents-postgres psql -U postgres -d agents -c \
		"SELECT id, status, error_message, created_at FROM web_jobs WHERE status = 'failed' ORDER BY created_at DESC LIMIT 10;"

db-shell: ## Open interactive database shell
	@docker exec -it agents-postgres psql -U postgres -d agents

shell: ## Open a Python shell with project context
	@echo "$(BLUE)Opening Python shell...$(NC)"
	$(UV) run python

shell-db: ## Open a database shell
	@echo "$(BLUE)Opening database shell...$(NC)"
	$(DOCKER_COMPOSE) exec postgres psql -U postgres -d agents

env-example: ## Show required environment variables
	@echo "$(BLUE)Required environment variables:$(NC)"
	@cat .env.example

generate-secret: ## Generate a secure secret key
	@echo "$(BLUE)Generated secret key:$(NC)"
	@$(PYTHON) -c "import secrets; print(secrets.token_urlsafe(32))"

generate-encryption-key: ## Generate a 32-byte encryption key
	@echo "$(BLUE)Generated encryption key:$(NC)"
	@$(PYTHON) -c "import secrets; print(secrets.token_urlsafe(24))"

# ============================================================================
# PRODUCTION
# ============================================================================

prod-check: ## Check production readiness
	@echo "$(BLUE)Checking production readiness...$(NC)"
	@echo ""
	@echo "Checking required environment variables..."
	@if [ -z "$$DATABASE_URL" ]; then echo "  $(RED)DATABASE_URL not set$(NC)"; else echo "  $(GREEN)DATABASE_URL set$(NC)"; fi
	@if [ -z "$$SECRET_KEY" ]; then echo "  $(RED)SECRET_KEY not set$(NC)"; else echo "  $(GREEN)SECRET_KEY set$(NC)"; fi
	@if [ -z "$$ENCRYPTION_KEY" ]; then echo "  $(RED)ENCRYPTION_KEY not set$(NC)"; else echo "  $(GREEN)ENCRYPTION_KEY set$(NC)"; fi
	@if [ -z "$$S3_ENDPOINT_URL" ]; then echo "  $(RED)S3_ENDPOINT_URL not set$(NC)"; else echo "  $(GREEN)S3_ENDPOINT_URL set$(NC)"; fi
	@if [ -z "$$AWS_ACCESS_KEY_ID" ]; then echo "  $(RED)AWS_ACCESS_KEY_ID not set$(NC)"; else echo "  $(GREEN)AWS_ACCESS_KEY_ID set$(NC)"; fi
	@if [ -z "$$AWS_SECRET_ACCESS_KEY" ]; then echo "  $(RED)AWS_SECRET_ACCESS_KEY not set$(NC)"; else echo "  $(GREEN)AWS_SECRET_ACCESS_KEY set$(NC)"; fi
	@echo ""
	@echo "Running code checks..."
	@make check || echo "$(RED)Code checks failed$(NC)"

prod-deploy: ## Deploy to production (customize as needed)
	@echo "$(YELLOW)Production deployment not configured.$(NC)"
	@echo "See docs/deployment/ for deployment guides."
