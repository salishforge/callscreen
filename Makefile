.PHONY: help install dev lint format typecheck test test-unit test-integration security run migrate docker-up docker-down clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	cd backend && pip install -e .

dev: ## Install development dependencies
	cd backend && pip install -e ".[dev,messaging]"

lint: ## Run linter
	cd backend && ruff check src/ tests/

format: ## Format code
	cd backend && ruff format src/ tests/

typecheck: ## Run type checker
	cd backend && mypy src/

test: ## Run all tests
	cd backend && pytest --cov=callscreen --cov-report=term-missing

test-unit: ## Run unit tests only
	cd backend && pytest -m unit --cov=callscreen

test-integration: ## Run integration tests only
	cd backend && pytest -m integration

security: ## Run security scans
	cd backend && bandit -r src/ -c pyproject.toml && safety check

run: ## Run development server
	cd backend && uvicorn callscreen.main:create_app --factory --reload --host 0.0.0.0 --port 8000

worker: ## Run Celery worker
	cd backend && celery -A callscreen.tasks.celery_app worker --loglevel=info

beat: ## Run Celery beat scheduler
	cd backend && celery -A callscreen.tasks.celery_app beat --loglevel=info

migrate: ## Run database migrations
	cd backend && alembic upgrade head

migrate-new: ## Create a new migration (usage: make migrate-new msg="description")
	cd backend && alembic revision --autogenerate -m "$(msg)"

docker-up: ## Start all services
	docker compose -f docker/docker-compose.yml up -d

docker-down: ## Stop all services
	docker compose -f docker/docker-compose.yml down

docker-build: ## Build Docker images
	docker compose -f docker/docker-compose.yml build

docker-logs: ## Tail service logs
	docker compose -f docker/docker-compose.yml logs -f

clean: ## Clean build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name *.egg-info -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/dist backend/build
