.PHONY: install test lint contract run baseline docker-build

install:
	python -m pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .

contract:
	python scripts/validate_ai_contract.py

run:
	uvicorn supportflow_ai.main:create_app --factory --reload --host 127.0.0.1 --port 8000

baseline:
	python -m evaluation.run_classification

docker-build:
	docker build -t supportflow-ai-service:local .
