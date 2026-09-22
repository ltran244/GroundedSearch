from psycopg_pool import AsyncConnectionPool

from app.config import settings

# open=False so importing this module never tries to reach the database.
# The pool is opened and closed by the lifespan in app.main, inside the event loop.
pool = AsyncConnectionPool(
    conninfo=settings.database_url,
    min_size=0,
    max_size=10,
    open=False,
)


async def get_connection():
    async with pool.connection() as conn:
        yield conn


async def check_database() -> None:
    """Run one query through the pool; raises if the database is unreachable."""
    async with pool.connection(timeout=2) as conn:
        await conn.execute("SELECT 1")
