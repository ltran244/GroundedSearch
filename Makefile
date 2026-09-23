.PHONY: dev lint format check test test-unit test-integration db db-down all
.PHONY: coverage coverage-html coverage-live test-live
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

# No database or network needed.
test-unit:
	uv run pytest tests/unit

# Needs `make db` and the test database migrated.
test-integration:
	uv run pytest tests/integration

# Real Gemini and Brave calls: costs credits. Needs `make db` too.
test-live:
	uv run pytest -m live

# --with pulls in pytest-cov for this command only, so it stays out of pyproject.
# Lists every uncovered line number per file.
coverage:
	uv run --with pytest-cov pytest --cov=app --cov-report=term-missing

# Same run, as a browsable report: open htmlcov/index.html
coverage-html:
	uv run --with pytest-cov pytest --cov=app --cov-report=html
	@echo "open htmlcov/index.html"

# Every test including the live ones, so app/db is covered too. Costs credits.
coverage-live:
	uv run --with pytest-cov pytest -m "" --cov=app --cov-report=term-missing

all: lint check test
