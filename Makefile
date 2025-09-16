.PHONY: help install dev test lint format clean run-api run-mcp demo

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	pip install -r requirements.txt

dev: ## Setup development environment
	python -m venv venv
	@echo "Virtual environment created. Activate with: source venv/bin/activate"
	@echo "Then run: make install"

test: ## Run all tests
	pytest app/tests/ -v

lint: ## Run linting
	ruff check app/
	mypy app/

format: ## Format code
	ruff format app/

clean: ## Clean temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -f .coverage

run-api: ## Run FastAPI server
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-mcp: ## Run MCP server
	python -m app.mcp_server

demo: ## Run MCP client demo
	python scripts/demo_mcp_client.py

docker-build: ## Build Docker image
	docker-compose build

docker-up: ## Run with Docker Compose
	docker-compose up

docker-down: ## Stop Docker containers
	docker-compose down
