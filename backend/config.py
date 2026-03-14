from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- YouTube ---
    YOUTUBE_API_KEY: str = ""

    # --- Twitch (reserved for future use — do not remove) ---
    TWITCH_CLIENT_ID: str = ""
    TWITCH_CLIENT_SECRET: str = ""

    # --- Data ---
    KAGGLE_CSV_PATH: str = "../data/campaigns.csv"

    # --- Database ---
    DATABASE_URL: str = "sqlite:///./hardscope.db"

    # --- Anthropic ---
    ANTHROPIC_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()