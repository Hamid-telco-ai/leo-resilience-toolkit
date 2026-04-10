from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LEO Resilience Studio API"
    app_version: str = "0.1.0"
    database_url: str = "postgresql+psycopg://leo:leo@localhost:5432/leo_resilience"
    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
