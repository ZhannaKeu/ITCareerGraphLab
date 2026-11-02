from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://career:career@localhost:5432/career"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
