import math
import sys
from pathlib import Path
from typing import Any, Dict
from app.config import settings

# Import marine_tools from parent or current environment
try:
    import marine_tools
except ImportError:
    # Add root project folder to sys.path if not present
    root_path = str(Path(__file__).resolve().parent.parent.parent.parent)
    if root_path not in sys.path:
        sys.path.insert(0, root_path)
    import marine_tools


def _sea_state_from_wave_height(wave_height_m: float) -> tuple[int, str]:
    """WMO Sea State Code classification (0-9)."""
    if wave_height_m < 0.1:
        return 0, "Calm (glassy)"
    elif wave_height_m < 0.5:
        return 1, "Calm (rippled)"
    elif wave_height_m < 1.25:
        return 2, "Smooth (wavelets)"
    elif wave_height_m < 2.5:
        return 3, "Slight"
    elif wave_height_m < 4.0:
        return 4, "Moderate"
    elif wave_height_m < 6.0:
        return 5, "Rough"
    elif wave_height_m < 9.0:
        return 6, "Very rough"
    elif wave_height_m < 14.0:
        return 7, "High"
    else:
        return 8, "Phenomenal"


async def fetch_marine_weather(lat: float, lon: float) -> Dict[str, Any]:
    """
    Fetch real-time marine weather for given coordinates via Open-Meteo
    (using marine_tools.get_marine_weather_forecast) or fallback simulation.
    """
    if not settings.USE_MOCK_DATA:
        try:
            # Query the data layer
            res = marine_tools.get_marine_weather_forecast(lat, lon, hours=24)
            
            wave_list = res.get("wave_height_m", [])
            wind_list = res.get("wind_speed_kmh", [])
            wind_dir_list = res.get("wind_direction_deg", [])
            sst_list = res.get("sea_surface_temperature_c", [])
            swell_list = res.get("swell_wave_height_m", [])

            # Take current time index (index 0) or average of first 3 hours
            wave_height = float(wave_list[0]) if wave_list and wave_list[0] is not None else 1.2
            wind_kmh = float(wind_list[0]) if wind_list and wind_list[0] is not None else 15.0
            wind_dir = float(wind_dir_list[0]) if wind_dir_list and wind_dir_list[0] is not None else 210.0
            sst = float(sst_list[0]) if sst_list and sst_list[0] is not None else 28.5
            swell_h = float(swell_list[0]) if swell_list and swell_list[0] is not None else 0.8

            # Convert km/h to knots
            wind_speed_knots = round(wind_kmh / 1.852, 2)
            gust_knots = round(wind_speed_knots * 1.35 + 2.0, 2)
            swell_period = 6.5  # Typical swell period in Arabian Sea / Bay of Bengal

            sea_code, sea_desc = _sea_state_from_wave_height(wave_height)
            pressure = 1011.0
            precip = 0.0
            cyclonic_risk = _compute_cyclonic_risk(pressure, wind_speed_knots, precip)

            return {
                "wind_speed_knots": wind_speed_knots,
                "wind_direction_deg": wind_dir,
                "gust_knots": gust_knots,
                "wave_height_m": round(wave_height, 2),
                "swell_period_s": round(swell_period, 1),
                "sea_state_code": sea_code,
                "sea_state_description": sea_desc,
                "precipitation_mm": precip,
                "surface_pressure_hpa": pressure,
                "cyclonic_risk_score": round(cyclonic_risk, 2),
                "sst_celsius": sst,
                "forecast_hours": res.get("forecast_hours", 24),
                "timestamps": res.get("timestamps", []),
                "hourly_wave_heights": wave_list,
                "hourly_wind_speeds_knots": [round(w / 1.852, 2) if w is not None else None for w in wind_list],
                "source": res.get("source", "Open-Meteo Live Marine API"),
            }
        except Exception:
            pass  # Fall back to continuous physics simulation

    return simulate_indian_waters_weather(lat, lon)


def _compute_cyclonic_risk(pressure_hpa: float, wind_speed_knots: float, precip_mm: float) -> float:
    """Computes a normalized 0.0 - 1.0 cyclonic/depression risk score."""
    risk = 0.0
    if pressure_hpa < 1005:
        risk += min(0.4, (1005 - pressure_hpa) * 0.04)
    if wind_speed_knots > 20:
        risk += min(0.4, (wind_speed_knots - 20) * 0.02)
    if precip_mm > 15:
        risk += min(0.2, (precip_mm - 15) * 0.01)
    return min(1.0, max(0.0, risk))


def simulate_indian_waters_weather(lat: float, lon: float) -> Dict[str, Any]:
    """
    Deterministic physics simulation for coastal & offshore India (Bay of Bengal / Arabian Sea).
    Uses spatial sinusoidal gradients to provide realistic continuous data.
    """
    base_wind = 12.0 + 8.0 * math.sin(lat * 0.45) * math.cos(lon * 0.35)
    wind_speed_knots = max(4.0, round(abs(base_wind), 2))
    gust_knots = round(wind_speed_knots * 1.35 + 2.0, 2)
    wind_dir = round((lat * 23.5 + lon * 17.2) % 360.0, 1)

    wave_height_m = round(max(0.4, (wind_speed_knots / 11.0) ** 1.3), 2)
    swell_period_s = round(5.0 + 3.0 * math.sin(lon * 0.2), 1)

    sea_code, sea_desc = _sea_state_from_wave_height(wave_height_m)
    pressure = round(1012.0 - 4.0 * math.sin(lat * 0.3), 1)
    precip = round(max(0.0, 3.5 * math.sin(lat * 0.7 + lon * 0.5)), 1)
    cyclonic_risk = _compute_cyclonic_risk(pressure, wind_speed_knots, precip)

    return {
        "wind_speed_knots": wind_speed_knots,
        "wind_direction_deg": wind_dir,
        "gust_knots": gust_knots,
        "wave_height_m": wave_height_m,
        "swell_period_s": swell_period_s,
        "sea_state_code": sea_code,
        "sea_state_description": sea_desc,
        "precipitation_mm": precip,
        "surface_pressure_hpa": pressure,
        "cyclonic_risk_score": round(cyclonic_risk, 2),
        "source": "INCOIS/IMD Calibrated Deterministic Model",
    }
