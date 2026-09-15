from psycopg.conninfo import make_conninfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    server_port: int
    database_name: str
    test_database_name: str
    database_host: str
    database_port: int
    database_user: str
    database_password: str
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
