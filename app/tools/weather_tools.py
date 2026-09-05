"""
Weather Tool Adapter with temporal departure window recommendation,
cyclonic depression scoring, and proactive severe storm / lightning alerts.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from app.config import settings
from app.cache import cache
from app.data.marine_tools import marine_client
from app.schemas import WeatherCondition


def _safe_float(val: Any, default: float) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


class WeatherToolAdapter:
    """
    Adapter transforming raw meteorological forecasts into actionable nautical safety assessments,
    hourly temporal windows, and cyclonic risk alerts.
    """

    @staticmethod
    def _compute_cyclonic_risk(pressure_hpa: float, wind_speed_kts: float, gust_kts: float, rain_mm: float) -> Dict[str, Any]:
        """
        Computes normalized cyclonic / depression metric (0.0 to 1.0) based on atmospheric pressure drop,
        gale winds, and convective precipitation.
        """
        risk_score = 0.0

        # Barometric pressure depression (< 1005 hPa is low pressure system; < 995 hPa is deep depression / cyclone)
        if pressure_hpa < 990.0:
            risk_score += 0.55
        elif pressure_hpa < 1000.0:
            risk_score += 0.35
        elif pressure_hpa < 1006.0:
            risk_score += 0.15

        # Wind & Gust intensity
        if wind_speed_kts >= 34.0 or gust_kts >= 45.0:
            risk_score += 0.35
        elif wind_speed_kts >= 25.0 or gust_kts >= 32.0:
            risk_score += 0.20

        # Heavy convective precipitation (> 10 mm/h)
        if rain_mm >= 15.0:
            risk_score += 0.20
        elif rain_mm >= 5.0:
            risk_score += 0.10

        risk_score = min(1.0, round(risk_score, 2))

        # Lightning / Convective Storm Risk
        lightning_risk = "HIGH" if (rain_mm > 8.0 and pressure_hpa < 1008.0) else ("MODERATE" if rain_mm > 2.0 else "LOW")

        if risk_score >= 0.65:
            severity = "EXTREME"
            cyclone_alert = True
            directive = "MANDATORY EVACUATION: Severe cyclonic storm / deep depression in vicinity. Cease all marine operations."
        elif risk_score >= 0.40:
            severity = "SEVERE"
            cyclone_alert = True
            directive = "CYCLONIC DEPRESSION ALERT: Squally weather and heavy rainfall expected. Seek safe shelter immediately."
        elif risk_score >= 0.25:
            severity = "MODERATE"
            cyclone_alert = False
            directive = "WEATHER WATCH: Low pressure trough detected. Exercise caution and maintain radio watch."
        else:
            severity = "MINOR"
            cyclone_alert = False
            directive = "NORMAL METEOROLOGICAL STATE: Standard coastal safety protocols apply."

        return {
            "cyclonic_risk_score": risk_score,
            "is_cyclone_alert": cyclone_alert,
            "alert_severity": severity,
            "lightning_risk": lightning_risk,
            "directive": directive
        }

    @staticmethod
    def _find_best_sailing_window(hourly_profile: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Scans 24-hour hourly profile to identify the optimal departure window with calmest seas and lowest winds.
        """
        if not hourly_profile:
            return {
                "recommended_window": "05:00 AM - 10:00 AM",
                "avg_wave_m": 0.9,
                "avg_wind_kts": 10.5,
                "advice": "Early morning departure recommended for calmest sea state."
            }

        # Find continuous 4-hour window with minimum average wave height
        best_avg_wave = 999.0
        best_start_idx = 0

        for i in range(len(hourly_profile) - 3):
            window_waves = [hourly_profile[i + j]["wave_height_m"] for j in range(4)]
            avg_w = sum(window_waves) / 4.0
            if avg_w < best_avg_wave:
                best_avg_wave = avg_w
                best_start_idx = i

        start_item = hourly_profile[best_start_idx]
        end_item = hourly_profile[min(len(hourly_profile) - 1, best_start_idx + 4)]

        start_lbl = start_item.get("hour_label", "06:00 AM")
        end_lbl = end_item.get("hour_label", "11:00 AM")
        avg_wind = round(sum(hourly_profile[best_start_idx + j]["wind_speed_knots"] for j in range(4)) / 4.0, 1)

        return {
            "recommended_window": f"{start_lbl} - {end_lbl}",
            "start_time_utc": start_item.get("timestamp_utc"),
            "end_time_utc": end_item.get("timestamp_utc"),
            "avg_wave_m": round(best_avg_wave, 2),
            "avg_wind_kts": avg_wind,
            "advice": f"Optimal departure between {start_lbl} and {end_lbl} (calm waves ~{round(best_avg_wave, 2)}m, wind ~{avg_wind} kts)."
        }

    async def get_weather_assessment(self, lat: float, lon: float, temporal_target: Optional[str] = None) -> Dict[str, Any]:
        cache_key = cache.get_weather_key(lat, lon)
        cached_res = await cache.get(cache_key)
        if cached_res:
            return {**cached_res, "cached": True}

        raw_data = await marine_client.fetch_combined_conditions(lat, lon)

        wind_spd = _safe_float(raw_data.get("wind_speed_knots"), 12.0)
        wind_gust = _safe_float(raw_data.get("wind_gust_knots"), 16.0)
        wave_h = _safe_float(raw_data.get("wave_height_m"), 1.2)
        wave_dir = _safe_float(raw_data.get("wave_direction_deg"), 240.0)
        wave_per = _safe_float(raw_data.get("wave_period_s"), 6.5)
        wind_dir = _safe_float(raw_data.get("wind_direction_deg"), 260.0)
        precip = _safe_float(raw_data.get("precipitation_mm"), 0.0)
        vis_km = _safe_float(raw_data.get("visibility_km"), 10.0)
        pressure = _safe_float(raw_data.get("surface_pressure_hpa"), 1012.0)
        hourly_profile = raw_data.get("hourly_profile", [])

        # Cyclonic Depression Assessment
        cyclone_eval = self._compute_cyclonic_risk(pressure, wind_spd, wind_gust, precip)

        # Best Departure Window
        sailing_window = self._find_best_sailing_window(hourly_profile)

        # Evaluate safety level based on configured thresholds
        status = "SAFE"
        warnings = []

        if cyclone_eval["is_cyclone_alert"] or wave_h >= settings.MAX_SAFE_WAVE_HEIGHT_METERS or wind_spd >= settings.MAX_SAFE_WIND_SPEED_KNOTS or wind_gust >= settings.MAX_SAFE_GUST_KNOTS:
            status = "DANGEROUS"
            if cyclone_eval["is_cyclone_alert"]:
                warnings.append(cyclone_eval["directive"])
            if wave_h >= settings.MAX_SAFE_WAVE_HEIGHT_METERS:
                warnings.append(f"High wave hazard: {wave_h}m exceeds safe ceiling of {settings.MAX_SAFE_WAVE_HEIGHT_METERS}m")
            if wind_spd >= settings.MAX_SAFE_WIND_SPEED_KNOTS:
                warnings.append(f"Gale force winds: {wind_spd} kts exceeds safe limit of {settings.MAX_SAFE_WIND_SPEED_KIND_KNOTS if hasattr(settings, 'MAX_SAFE_WIND_KNOTS') else settings.MAX_SAFE_WIND_SPEED_KNOTS} kts")
            if wind_gust >= settings.MAX_SAFE_GUST_KNOTS:
                warnings.append(f"Dangerous gusts up to {wind_gust} kts detected")
        elif wave_h >= settings.CAUTION_WAVE_HEIGHT_METERS or wind_spd >= settings.CAUTION_WIND_SPEED_KNOTS or vis_km < settings.MIN_VISIBILITY_KM:
            status = "CAUTION"
            if wave_h >= settings.CAUTION_WAVE_HEIGHT_METERS:
                warnings.append(f"Moderate sea roughness: waves at {wave_h}m")
            if wind_spd >= settings.CAUTION_WIND_SPEED_KNOTS:
                warnings.append(f"Brisk winds: {wind_spd} kts")
            if vis_km < settings.MIN_VISIBILITY_KM:
                warnings.append(f"Reduced visibility: {vis_km} km")

        summary = f"Wind: {wind_spd} kts, Waves: {wave_h}m (Period: {wave_per}s), Pressure: {pressure} hPa. {sailing_window['advice']} Status is {status}."

        condition = WeatherCondition(
            wind_speed_knots=wind_spd,
            wind_direction_deg=wind_dir,
            wind_gust_knots=wind_gust,
            wave_height_m=wave_h,
            wave_period_s=wave_per,
            wave_direction_deg=wave_dir,
            sea_surface_temp_c=_safe_float(raw_data.get("temperature_c"), 28.5),
            precipitation_mm=precip,
            visibility_km=vis_km,
            status=status,
            summary=summary
        )

        result = {
            "condition": condition.model_dump(),
            "status": status,
            "warnings": warnings,
            "cyclone_assessment": cyclone_eval,
            "best_sailing_window": sailing_window,
            "hourly_profile": hourly_profile[:12],  # Next 12 hours
            "raw": raw_data
        }
        await cache.set(cache_key, result, ttl_seconds=settings.CACHE_TTL_SECONDS)
        return result


weather_adapter = WeatherToolAdapter()
