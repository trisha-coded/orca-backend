from datetime import datetime, timezone
from typing import Any, Dict
from app.state import MarineAgentState
from app.tools.weather_tools import fetch_marine_weather
from app.tools.ocean_tools import fetch_oceanographic_data
from app.tools.geofence_tools import check_geofence_and_imbl


async def weather_agent_node(state: MarineAgentState) -> MarineAgentState:
    """Domain Agent 1: Meteorology & Sea State Intelligence."""
    coords = state.get("coordinates", {})
    lat = float(coords.get("latitude", 9.28))
    lon = float(coords.get("longitude", 79.31))
    vessel = state.get("vessel_context", {})

    weather_res = await fetch_marine_weather(lat, lon)

    # Check vessel-specific wave and wind limits
    max_safe_wave = float(vessel.get("max_safe_wave_m", 3.0))
    max_safe_wind = float(vessel.get("max_safe_wind_knots", 25.0))

    is_safe = (
        weather_res["wave_height_m"] <= max_safe_wave
        and weather_res["wind_speed_knots"] <= max_safe_wind
        and weather_res["cyclonic_risk_score"] < 0.6
    )

    advisory_notes = []
    if weather_res["wave_height_m"] > max_safe_wave:
        advisory_notes.append(
            f"Wave height of {weather_res['wave_height_m']}m exceeds vessel safety threshold ({max_safe_wave}m)."
        )
    if weather_res["wind_speed_knots"] > max_safe_wind:
        advisory_notes.append(
            f"Wind speed of {weather_res['wind_speed_knots']} knots exceeds vessel threshold ({max_safe_wind} knots)."
        )
    if weather_res["cyclonic_risk_score"] >= 0.4:
        advisory_notes.append("Elevated cyclonic depression risk detected in regional quadrant.")

    weather_res["is_safe"] = is_safe
    weather_res["advisory_notes"] = advisory_notes

    audit_trail = list(state.get("audit_trail", []))
    audit_trail.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "WeatherAgent",
        "stage": "domain_analysis",
        "action": "EVALUATE_MARINE_WEATHER",
        "details": {
            "wind_speed_knots": weather_res["wind_speed_knots"],
            "wave_height_m": weather_res["wave_height_m"],
            "sea_state": weather_res["sea_state_description"],
            "is_safe": is_safe,
        },
    })

    return {
        **state,
        "weather_data": weather_res,
        "audit_trail": audit_trail,
    }


async def ocean_agent_node(state: MarineAgentState) -> MarineAgentState:
    """Domain Agent 2: Oceanography & Potential Fishing Zone (PFZ) Intelligence."""
    coords = state.get("coordinates", {})
    lat = float(coords.get("latitude", 9.28))
    lon = float(coords.get("longitude", 79.31))
    target_species = state.get("target_species")

    ocean_res = await fetch_oceanographic_data(lat, lon, target_species=target_species)

    audit_trail = list(state.get("audit_trail", []))
    audit_trail.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "OceanAgent",
        "stage": "domain_analysis",
        "action": "ANALYZE_PFZ_AND_OCEANOGRAPHY",
        "details": {
            "sst_celsius": ocean_res.get("sst_celsius"),
            "chlorophyll_mg_m3": ocean_res.get("chlorophyll_mg_m3"),
            "pfz_detected": ocean_res.get("pfz_detected"),
            "pfz_confidence": ocean_res.get("pfz_confidence"),
            "recommended_zones_count": len(ocean_res.get("recommended_fishing_zones") or []),
            "is_mock_data": ocean_res.get("is_mock_data", False),
        },
    })

    return {
        **state,
        "ocean_data": ocean_res,
        "audit_trail": audit_trail,
    }


def geofence_agent_node(state: MarineAgentState) -> MarineAgentState:
    """Domain Agent 3: Maritime Geofencing & International Boundary Protection."""
    coords = state.get("coordinates", {})
    lat = float(coords.get("latitude", 9.28))
    lon = float(coords.get("longitude", 79.31))
    vessel = state.get("vessel_context", {})
    vessel_type = vessel.get("vessel_type", "mechanized_trawler")

    geofence_res = check_geofence_and_imbl(lat, lon, vessel_type=vessel_type)

    audit_trail = list(state.get("audit_trail", []))
    audit_trail.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "GeofenceAgent",
        "stage": "domain_analysis",
        "action": "EVALUATE_IMBL_AND_MPA_BOUNDARIES",
        "details": {
            "nearest_imbl": geofence_res["nearest_imbl_name"],
            "distance_to_imbl_nm": geofence_res["distance_to_imbl_nm"],
            "buffer_alert_level": geofence_res["buffer_alert_level"],
            "inside_mpa": geofence_res["inside_mpa"],
        },
    })

    return {
        **state,
        "geofence_data": geofence_res,
        "audit_trail": audit_trail,
    }
