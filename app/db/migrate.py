"""Run Yoyo using the application's existing environment settings."""

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

from app.config import settings


def main() -> int:
    args = sys.argv[1:]
    use_test_database = bool(args and args[0] == "--test")
    if use_test_database:
        args.pop(0)
        if settings.test_database_name == settings.database_name:
            raise ValueError("Test database must differ from the application database")
    database = (
        settings.test_database_name if use_test_database else settings.database_name
    )
    env = os.environ.copy()
    env.update(
        PGHOST=settings.database_host,
        PGPORT=str(settings.database_port),
        PGUSER=settings.database_user,
        PGPASSWORD=settings.database_password,
        PGCONNECT_TIMEOUT="5",
        YOYO_DATABASE_URL=f"postgresql+psycopg:///{quote(database, safe='')}",
    )
    executable = Path(sys.executable).parent / "yoyo"
    result = subprocess.run([str(executable), *args], env=env, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
