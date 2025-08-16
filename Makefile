# Dental Backend Makefile
# Provides common development and deployment commands

.PHONY: help build test lint run clean install dev-setup docker-build docker-run

# Default target
help:
	@echo "Dental Backend - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  install      - Install all dependencies"
	@echo "  dev-setup    - Set up development environment"
	@echo "  build        - Build all packages and services"
	@echo "  test         - Run all tests"
	@echo "  lint         - Run linting and type checking"
	@echo "  run          - Run the API service"
	@echo "  run-worker   - Run the background worker"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build - Build Docker images"
	@echo "  docker-run   - Run services with Docker Compose"
	@echo ""
	@echo "Utilities:"
	@echo "  clean        - Clean build artifacts"
	@echo "  format       - Format code with Black"
	@echo "  check-format - Check code formatting"

# Development setup
install:
	@echo "Installing dependencies..."
	pip3 install -r requirements.txt
	pip3 install -r requirements-dev.txt

dev-setup:
	@echo "Setting up development environment..."
	python -m venv .venv
	@echo "Virtual environment created. Activate with: source .venv/bin/activate"
	@echo "Then run: make install"

# Build targets
build:
	@echo "Building packages..."
	cd packages/common && pip3 install -e .
	cd services/api && pip3 install -e .
	cd services/worker && pip3 install -e .

# Testing
test:
	@echo "Running tests..."
	pytest tests/ -v --cov=dental_backend --cov-report=html --cov-report=term-missing

test-unit:
	@echo "Running unit tests..."
	pytest tests/unit/ -v

test-integration:
	@echo "Running integration tests..."
	pytest tests/integration/ -v

# Linting and formatting
lint:
	@echo "Running linting checks..."
	ruff check .
	@echo "Linting complete!"

lint-full:
	@echo "Running full linting checks (including type checking and security)..."
	ruff check .
	mypy dental_backend/
	bandit -r dental_backend/ -f json -o bandit-report.json
	@echo "Full linting complete!"

format:
	@echo "Formatting code..."
	black .
	ruff check --fix .

check-format:
	@echo "Checking code formatting..."
	black --check .
	ruff check .

# Running services
run:
	@echo "Starting API service..."
	cd services/api && uvicorn dental_backend.api.main:app --reload --host 0.0.0.0 --port 8000

run-worker:
	@echo "Starting background worker..."
	cd services/worker && celery -A dental_backend.worker.celery worker --loglevel=info

run-all:
	@echo "Starting all services..."
	docker-compose up

# Docker commands
docker-build:
	@echo "Building Docker images..."
	docker-compose build

docker-run:
	@echo "Running services with Docker Compose..."
	docker-compose up -d

docker-stop:
	@echo "Stopping Docker services..."
	docker-compose down

# Database commands
db-migrate:
	@echo "Running database migrations..."
	alembic upgrade head

db-rollback:
	@echo "Rolling back database migration..."
	alembic downgrade -1

db-reset:
	@echo "Resetting database..."
	alembic downgrade base
	alembic upgrade head

# Utility commands
clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf build/ dist/ .coverage htmlcov/

# Security checks
security-check:
	@echo "Running security checks..."
	bandit -r dental_backend/
	safety check

# Performance checks
performance-check:
	@echo "Running performance checks..."
	python -m cProfile -o profile.stats scripts/performance_test.py

# Documentation
docs:
	@echo "Generating documentation..."
	pdoc --html dental_backend --output-dir docs/

# Pre-commit hooks
pre-commit:
	@echo "Running pre-commit checks..."
	make check-format
	make lint
	make test-unit

pre-commit-fast:
	@echo "Running fast pre-commit checks..."
	pre-commit run --all-files
