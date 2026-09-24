from psycopg.conninfo import make_conninfo
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_name: str
    test_database_name: str
    database_host: str
    database_port: int
    database_user: str
    database_password: str
    redis_host: str = "localhost"
    redis_port: int = 6379
    # How many jobs one worker runs at once, and how long one may take.
    worker_max_jobs: int = Field(default=2, ge=1)
    worker_job_timeout_seconds: int = Field(default=600, ge=1)
    # A job still 'running' this long after it started has lost its worker.
    stale_job_minutes: int = Field(default=10, ge=1)
    google_api_key: SecretStr | None = None
    brave_search_api_key: SecretStr | None = None
    brave_max_concurrent_requests: int = Field(default=4, ge=1)
    brave_results_per_query: int = Field(default=5, ge=1, le=20)
    llm_model: str = "gemini-3.5-flash-lite"
    llm_max_concurrent_requests: int = Field(default=4, ge=1)
    embedding_model: str = "gemini-embedding-001"
    # Must match the vector(...) size in the chunks migration. Changing it
    # means re-embedding everything.
    embedding_dimensions: int = Field(default=768, ge=1, le=2000)
    # Retrieve more chunks than the answer needs, so the per-source cap has
    # something to drop.
    retrieval_candidates: int = Field(default=20, ge=1)
    retrieval_chunks: int = Field(default=10, ge=1)
    retrieval_chunks_per_source: int = Field(default=3, ge=1)
    # To load environment variables from the .env file
    model_config = SettingsConfigDict(env_file=".env")

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.database_user}:{self.database_password}@{self.database_host}:{self.database_port}/{self.database_name}"

    @property
    def test_database_url(self) -> str:
        if self.test_database_name == self.database_name:
            raise ValueError("Test database must differ from the application database")
        return make_conninfo(
            host=self.database_host,
            port=self.database_port,
            user=self.database_user,
            password=self.database_password,
            dbname=self.test_database_name,
        )


settings = Settings()  # pyright: ignore[reportCallIssue]
