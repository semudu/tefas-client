.PHONY: install test lint format build clean publish

install:
	uv pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check src tests
	mypy src

format:
	ruff format src tests
	ruff check --fix src tests

build: clean
	hatch build

clean:
	rm -rf dist/ .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete

publish: build
	hatch publish