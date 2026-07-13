from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://tospec:tospec@db:5432/tospec"
    cors_origins: str = "http://localhost,http://localhost:5500,http://127.0.0.1:5500,null"
    max_file_size_mb: int = 15
    max_batch_files: int = 30
    rate_limit_resize: str = "20/minute"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
