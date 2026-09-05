"""
Configuration and marine safety thresholds for the Oceanova backend.
"""

from typing import List
import os

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseModel as BaseSettings  # fallback if pydantic-settings not yet installed


class Settings(BaseSettings):
    # App Settings
    PROJECT_NAME: str = "Oceanova Marine Intelligence Backend"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ALLOWED_ORIGINS: List[str] = ["*"]

    # Redis / Caching
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 900  # 15 minutes TTL for spatial queries
    SPATIAL_CACHE_PRECISION: int = 2  # Coordinates rounded to 2 decimals (~1.1 km grid) for spatial query caching

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Marine Safety Thresholds
    MAX_SAFE_WIND_SPEED_KNOTS: float = 25.0       # > 25 knots is Dangerous
    CAUTION_WIND_SPEED_KNOTS: float = 18.0        # 18-25 knots is Caution
    MAX_SAFE_WAVE_HEIGHT_METERS: float = 2.5      # > 2.5m is Dangerous
    CAUTION_WAVE_HEIGHT_METERS: float = 1.8       # 1.8-2.5m is Caution
    DANGEROUS_WAVE_HEIGHT_METERS: float = 3.5     # Extreme warning
    MAX_SAFE_GUST_KNOTS: float = 30.0             # > 30 knots gusts is Dangerous
    MIN_VISIBILITY_KM: float = 4.0                # < 4km is Low Visibility

    # Ocean Conditions & Potential Fishing Zone (PFZ)
    MIN_OPTIMAL_SST_CELSIUS: float = 26.0         # Tropical Indian Ocean PFZ range
    MAX_OPTIMAL_SST_CELSIUS: float = 30.5
    MIN_CHLOROPHYLL_MG_M3: float = 0.2            # Minimum chlorophyll concentration for plankton bloom
    OPTIMAL_CHLOROPHYLL_MG_M3: float = 0.6

    # Geofence & Boundary Limits
    EEZ_WARNING_BUFFER_NM: float = 5.0            # Alert when within 5 nautical miles of maritime border
    EEZ_DANGER_BUFFER_NM: float = 1.0             # High alert within 1 NM of international border

    # Live APIs
    OPEN_METEO_MARINE_API: str = "https://marine-api.open-meteo.com/v1/marine"
    OPEN_METEO_WEATHER_API: str = "https://api.open-meteo.com/v1/forecast"

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"
    }


settings = Settings()
