from psycopg_pool import ConnectionPool

from app.config import settings

# open=False so importing this module never tries to reach the database.
pool = ConnectionPool(
    conninfo=settings.Database_URL(),
    min_size=1,
    max_size=10,
    open=False,
)


def get_connection():
    with pool.connection() as conn:
        yield conn
