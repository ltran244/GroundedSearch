# Migrations

Yoyo is installed in the project's virtual environment by `uv sync`. No global
installation or migration container is needed. Run commands from the repository
root; the launcher reads the existing `.env` settings.

```bash
make migration-new name=create_research_jobs
make migration-status
make migrate

make migration-status-test
make migrate-test
uv run pytest -m integration
```

`migration-new` generates a SQL file without opening an editor. Write your SQL
in it and preserve the `-- depends:` comment. For rollback, create a separate
file with the same stem and a `.rollback.sql` suffix. Creating a file does not
apply it. Do not edit migrations already applied to shared databases.

The default target is `DATABASE_NAME`; commands ending in `-test` use
`TEST_DATABASE_NAME`. The launcher rejects matching names for test commands.
Both databases must already exist. Start local Postgres with `make db`.
Yoyo tracks applied migrations in its own tables in each database and applies
files in dependency then filename order.

`app/db/migrate.py` only passes your existing settings to Yoyo via environment
variables. Yoyo handles migration execution and tracking using psycopg 3.
`yoyo.ini` contains no credentials.

```bash
make migration-rollback-test
make migration-rollback
```

Rollback is interactive so you can review the selected migrations. It does not
restore deleted data. Migrations do not run automatically during app startup.

CI can run `uv sync --locked`, supply its test database connection settings,
then run pytest. Integration fixtures apply pending test-database migrations
automatically; `make migrate-test` remains available for manual use.
The same SQL files run in both environments.

See the [Yoyo documentation](https://ollycope.com/software/yoyo/latest/).

## Test cleanup

Tests using `integration_client`, `integration_pool`, or `clean_test_database`
first apply pending Yoyo migrations once per pytest session. Already applied
migrations are skipped; migration failures stop fixture setup.

Tests using `integration_client` or `integration_pool` automatically clear
application records before and after each test, including failed tests. Raw SQL
tests should request the `clean_test_database` fixture. Mock tests need no database.

Cleanup truncates application tables in `public` and resets their owned identity
sequences. It preserves tables, constraints, Yoyo metadata, and extension-owned
tables. Seed/reference rows are also cleared; create any needed data in fixtures.
The connected database name is checked before cleanup. Cleanup uses an independent
connection so closing the app pool during a test does not prevent it.

Run these integration tests sequentially against a dedicated test database.
Parallel workers need separate databases. New application schemas beyond `public`
will require extending cleanup. If Postgres is unavailable during teardown,
cleanup reports an error; the next run cleans again before tests start.
