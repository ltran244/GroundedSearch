from typing import Any
from pydantic import BaseModel

class ErrorResponse(BaseModel):
    detail: str

DATABASE_UNAVAILABLE: dict[int | str, dict[str, Any]] = {
    503: {
                  "model": ErrorResponse,
                  "description": "Database unavailable",
                  "content": {
                      "application/json": {
                          "example": {"detail": "Database unavailable"}
                      }
                  },
              }
}

RESEARCH_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {
        "model": ErrorResponse,
        "description": "Research job not found",
        "content": {
            "application/json": {
                "example": {"detail": "Research job not found"}
            }
        },
    }
}