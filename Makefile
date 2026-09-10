.PHONY: dev lint format check test db db-down all

dev:
	uv run fastapi dev

db:
	docker compose up -d db

db-down:
	docker compose down

lint:
	uv run ruff check .

format:
	uv run ruff check --fix .
	uv run ruff format .

check:
	uv run pyright

test:
	uv run pytest

all: lint check test
