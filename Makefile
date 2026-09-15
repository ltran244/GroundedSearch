.PHONY: dev lint format check test db db-down all
.PHONY: migration-new migrate migrate-test migration-status migration-status-test
.PHONY: migration-rollback migration-rollback-test

YOYO = uv run python -m app.db.migrate

dev:
	uv run fastapi dev

db:
	docker compose up -d db

db-down:
	docker compose down

migration-new:
	@test -n "$(name)" || (echo 'Usage: make migration-new name=create_research_jobs'; exit 1)
	$(YOYO) new --sql --batch --message "$(name)"

migrate:
	$(YOYO) apply --batch

migrate-test:
	$(YOYO) --test apply --batch

migration-status:
	$(YOYO) list

migration-status-test:
	$(YOYO) --test list

migration-rollback:
	$(YOYO) rollback

migration-rollback-test:
	$(YOYO) --test rollback

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
