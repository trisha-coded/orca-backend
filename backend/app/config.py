import os
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    # Project Information
    PROJECT_NAME: str = "Agentic Marine Intelligence Platform"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: Union[List[str], str] = ["*"]

    # LLM Configurations
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    DEFAULT_LLM_MODEL: str = "gemini-1.5-flash"
    DEFAULT_TEMPERATURE: float = 0.2

    # Live Data / Simulation Modes
    # When False, queries real-time Open-Meteo Marine APIs with graceful fallback
    USE_MOCK_DATA: bool = False
    IMBL_CRITICAL_BUFFER_NM: float = 3.0  # Nautical miles
    IMBL_WARNING_BUFFER_NM: float = 7.0   # Nautical miles
    MAX_SAFE_WAVE_HEIGHT_M: float = 3.5   # Meters
    MAX_SAFE_WIND_SPEED_KNOTS: float = 28.0  # Knots
    MAX_CYCLONIC_RISK_INDEX: float = 0.6  # Scale 0.0 to 1.0

    # Model config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        return ["*"]


settings = Settings()
