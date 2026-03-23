import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_path: str = "data/channels.db"
    refresh_interval_minutes: int = 30
    max_concurrent_resolves: int = 5
    fail_threshold: int = 3
    resolve_timeout_seconds: int = 30
    health_check_timeout_seconds: int = 5

    model_config = {"env_file": ".env", "case_sensitive": False}


settings = Settings()
