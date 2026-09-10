from fastapi import APIRouter, HTTPException, status

from app.db.pool import pool

health_router = APIRouter()


@health_router.get("/healthz")
def health_check():
    """To check if the server is up and running"""
    return {"status": "ok"}


@health_router.get(
    "/readyz",
    responses={
      
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Service Unavailable"}
    },
)
def readiness_check():
    """To check if the server can reach the database or database is online"""
    try:
        with pool.connection(timeout=2) as conn, conn.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc
    return {status.HTTP_200_OK: "Service Available"}
