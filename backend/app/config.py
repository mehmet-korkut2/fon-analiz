from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./fon.db"
    frontend_url: str = "http://localhost:5173"

    # Günlük TEFAS güncellemesi
    scheduler_enabled: bool = True
    update_hour: int = 21
    update_minute: int = 0
    timezone: str = "Europe/Istanbul"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
