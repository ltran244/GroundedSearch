from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    server_port: int
    database_name: str
    database_host: str
    database_port: int
    database_user: str
    database_password: str
    # To load environment variables from the .env file
    model_config = SettingsConfigDict(env_file=".env")

    def Database_URL(self) -> str:
        return f"postgresql://{self.database_user}:{self.database_password}@{self.database_host}:{self.database_port}/{self.database_name}"


settings = Settings()
