"""
Marine / Geospatial Data Layer — Agentic Marine Intelligence Platform (MVP)

This module provides three plain-Python functions that form the data backbone
for the Smart India Hackathon "Agentic Marine Intelligence Platform":

  1. get_marine_weather_forecast  — live marine + wind forecast via Open-Meteo
  2. check_maritime_boundaries    — EEZ point-in-polygon check via GeoPandas
  3. get_pfz_and_ocean_conditions — real SST / chlorophyll + derived fishing zones

Data sources:
  • Weather:    Open-Meteo Marine & Forecast APIs (live, no key required)
  • Boundaries: Marine Regions World EEZ v12 — filtered GeoJSON for India,
                Sri Lanka, Pakistan, Bangladesh
  • PFZ/Ocean:  Copernicus Marine Service (real SST + chlorophyll) via
                copernicus_ocean.py; fishing zones are AI-derived, not official INCOIS PFZ

These functions are intentionally kept as plain functions (no classes, no
decorators, no async) so that a teammate can later wrap them as
LangChain / LangGraph tools with minimal changes.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import copernicusmarine
import geopandas as gpd
import numpy as np
import requests
from shapely.geometry import Point
from shapely.ops import unary_union

import copernicus_ocean as _cm
from copernicus_ocean import get_real_chlorophyll, get_real_sst

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MARINE_API_URL = "https://marine-api.open-meteo.com/v1/marine"
_FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"
_REQUEST_TIMEOUT = 10  # seconds

_MAX_FORECAST_HOURS = 168  # 7 days — Open-Meteo provides up to ~16 days

# Projected CRS used for distance calculations around the Indian coast.
# EPSG:32643 — WGS 84 / UTM zone 43N — covers 72°E–78°E, which encompasses
# the western Indian coastline including Mangalore, Goa, and Mumbai.
# Good enough for an MVP; a proper pipeline would pick the zone dynamically.
_METRIC_CRS = "EPSG:32643"

_GEOJSON_PATH = Path(__file__).resolve().parent / "india_neighbors_eez.geojson"

# Module-level cache so we don't re-read 8 MB of GeoJSON on every call.
_eez_gdf: gpd.GeoDataFrame | None = None

# Module-level cache for the per-sovereign unified geometries (both in
# EPSG:4326 for containment checks and reprojected for distance checks).
# Without this, check_maritime_boundaries() would redo a groupby + unary_union
# over the full EEZ geometries on every single call.
_unified_countries_4326: gpd.GeoDataFrame | None = None
_unified_countries_proj: gpd.GeoDataFrame | None = None

# Fishing-suitability scoring thresholds (see PFZ_Ocean_Data_Research_Report.md).
_FRONT_GRADIENT_THRESHOLD_C_PER_KM = 0.06
_TOP_N_ZONES = 5
_MIN_ZONE_SEPARATION_KM = 5.0

_PFZ_DISCLAIMER = (
    "recommended_fishing_zones is an experimental, data-derived suitability "
    "estimate based on real SST and chlorophyll observations. It is NOT an "
    "official INCOIS Potential Fishing Zone (PFZ) advisory."
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_lat_lon(lat: float, lon: float) -> None:
    """Raise ValueError if lat/lon are out of range."""
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        raise ValueError(f"lat and lon must be numbers, got lat={type(lat).__name__}, lon={type(lon).__name__}")
    if not (-90 <= lat <= 90):
        raise ValueError(f"Latitude must be between -90 and 90, got {lat}")
    if not (-180 <= lon <= 180):
        raise ValueError(f"Longitude must be between -180 and 180, got {lon}")


def _validate_hours(hours: int) -> int:
    """Validate and clamp *hours*; return the cleaned value."""
    if not isinstance(hours, int):
        raise ValueError(f"hours must be a positive integer, got {type(hours).__name__}")
    if hours <= 0:
        raise ValueError(f"hours must be > 0, got {hours}")
    if hours > _MAX_FORECAST_HOURS:
        hours = _MAX_FORECAST_HOURS
    return hours


# ---------------------------------------------------------------------------
# EEZ loader (internal)
# ---------------------------------------------------------------------------

def _load_eez() -> gpd.GeoDataFrame:
    """Load (and cache) the filtered EEZ GeoJSON."""
    global _eez_gdf
    if _eez_gdf is not None:
        return _eez_gdf

    if not _GEOJSON_PATH.exists():
        raise FileNotFoundError(
            f"EEZ GeoJSON not found at {_GEOJSON_PATH}. "
            "Please place india_neighbors_eez.geojson next to marine_tools.py."
        )
    _eez_gdf = gpd.read_file(_GEOJSON_PATH)
    return _eez_gdf


def _load_unified_countries() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    Build (and cache) one merged geometry per sovereign country, both in
    EPSG:4326 (for containment checks) and reprojected to _METRIC_CRS
    (for distance checks). Computed once per process, not once per call.
    """
    global _unified_countries_4326, _unified_countries_proj
    if _unified_countries_4326 is not None and _unified_countries_proj is not None:
        return _unified_countries_4326, _unified_countries_proj

    eez = _load_eez()
    countries: dict[str, Any] = {
        sovereign: unary_union(group.geometry)
        for sovereign, group in eez.groupby("SOVEREIGN1")
    }
    gdf_4326 = gpd.GeoDataFrame(
        {"country": list(countries.keys())},
        geometry=list(countries.values()),
        crs="EPSG:4326",
    )
    gdf_proj = gdf_4326.to_crs(_METRIC_CRS)

    _unified_countries_4326 = gdf_4326
    _unified_countries_proj = gdf_proj
    return gdf_4326, gdf_proj


# ===================================================================
# FUNCTION 1 — Marine Weather Forecast
# ===================================================================

def get_marine_weather_forecast(
    lat: float,
    lon: float,
    hours: int = 24,
) -> dict[str, Any]:
    """
    Retrieve a marine weather forecast for a given location.

    Parameters
    ----------
    lat : float
        Latitude (-90 to 90).
    lon : float
        Longitude (-180 to 180).
    hours : int, optional
        Number of forecast hours to return (default 24, max 168).

    Returns
    -------
    dict
        Forecast data including wave heights, wind speed/direction,
        timestamps, units, and source attribution.

    Data sources
    ------------
    • Marine data:  https://marine-api.open-meteo.com/v1/marine
    • Wind data:    https://api.open-meteo.com/v1/forecast

    Limitations
    -----------
    • No cyclone or lightning alerts — those require separate data sources.
    • Open-Meteo is a free service; very high request rates may be throttled.
    """
    _validate_lat_lon(lat, lon)
    hours = _validate_hours(hours)

    # --- Marine API (wave data) -------------------------------------------
    marine_params: dict[str, Any] = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "wave_height,wind_wave_height,swell_wave_height,sea_surface_temperature",
    }
    try:
        marine_resp = requests.get(
            _MARINE_API_URL, params=marine_params, timeout=_REQUEST_TIMEOUT,
        )
        marine_resp.raise_for_status()
        marine_data = marine_resp.json()
    except requests.ConnectionError as exc:
        raise ConnectionError(f"Cannot reach Open-Meteo Marine API: {exc}") from exc
    except requests.Timeout as exc:
        raise ConnectionError(f"Open-Meteo Marine API timed out: {exc}") from exc
    except requests.HTTPError as exc:
        raise RuntimeError(f"Open-Meteo Marine API HTTP error: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"Open-Meteo Marine API returned invalid JSON: {exc}") from exc

    hourly_marine = marine_data.get("hourly")
    if not hourly_marine:
        raise RuntimeError("Open-Meteo Marine API response missing 'hourly' data.")

    # --- Forecast API (wind data) -----------------------------------------
    wind_params: dict[str, Any] = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "windspeed_10m,winddirection_10m",
        "wind_speed_unit": "kmh",
    }
    try:
        wind_resp = requests.get(
            _FORECAST_API_URL, params=wind_params, timeout=_REQUEST_TIMEOUT,
        )
        wind_resp.raise_for_status()
        wind_data = wind_resp.json()
    except requests.ConnectionError as exc:
        raise ConnectionError(f"Cannot reach Open-Meteo Forecast API: {exc}") from exc
    except requests.Timeout as exc:
        raise ConnectionError(f"Open-Meteo Forecast API timed out: {exc}") from exc
    except requests.HTTPError as exc:
        raise RuntimeError(f"Open-Meteo Forecast API HTTP error: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"Open-Meteo Forecast API returned invalid JSON: {exc}") from exc

    hourly_wind = wind_data.get("hourly")
    if not hourly_wind:
        raise RuntimeError("Open-Meteo Forecast API response missing 'hourly' data.")

    # --- Trim to requested hours ------------------------------------------
    timestamps = hourly_marine.get("time", [])[:hours]
    wave_height = hourly_marine.get("wave_height", [])[:hours]
    wind_wave_height = hourly_marine.get("wind_wave_height", [])[:hours]
    swell_wave_height = hourly_marine.get("swell_wave_height", [])[:hours]
    sea_surface_temp = hourly_marine.get("sea_surface_temperature", [])[:hours]
    wind_speed = hourly_wind.get("windspeed_10m", [])[:hours]
    wind_direction = hourly_wind.get("winddirection_10m", [])[:hours]

    return {
        "location": {"latitude": lat, "longitude": lon},
        "forecast_hours": len(timestamps),
        "timestamps": timestamps,
        "wave_height_m": wave_height,
        "wind_wave_height_m": wind_wave_height,
        "swell_wave_height_m": swell_wave_height,
        "sea_surface_temperature_c": sea_surface_temp,
        "wind_speed_kmh": wind_speed,
        "wind_direction_deg": wind_direction,
        "units": {
            "wave_height": "m",
            "wind_wave_height": "m",
            "swell_wave_height": "m",
            "sea_surface_temperature": "°C",
            "wind_speed": "km/h",
            "wind_direction": "degrees",
        },
        "source": "Open-Meteo (SST relayed from MeteoFrance/Copernicus GLOBAL_ANALYSISFORECAST_PHY, ~8km resolution)",
    }


# ===================================================================
# FUNCTION 2 — Maritime Boundaries
# ===================================================================

def check_maritime_boundaries(
    lat: float,
    lon: float,
) -> dict[str, Any]:
    """
    Check whether a point falls inside India's EEZ and find the nearest
    EEZ boundary among India, Sri Lanka, Pakistan, and Bangladesh.

    Parameters
    ----------
    lat : float
        Latitude (-90 to 90).
    lon : float
        Longitude (-180 to 180).

    Returns
    -------
    dict
        Boundary check results including inside/outside India EEZ,
        nearest EEZ country, distance to nearest boundary in km,
        and source attribution.

    Data source
    -----------
    Marine Regions World EEZ v12 — filtered GeoJSON (EPSG:4326).

    Distance calculation
    --------------------
    Geometries are reprojected to EPSG:32643 (UTM 43N) to compute
    distances in metres.  This zone covers 72°E–78°E and is appropriate
    for India's west coast.  An operational system would select the UTM
    zone dynamically.

    Limitations
    -----------
    • Does NOT include Navy restricted zones, MPAs, or cyclone zones.
    • Only four countries (India, Sri Lanka, Pakistan, Bangladesh).
    """
    _validate_lat_lon(lat, lon)

    point_4326 = Point(lon, lat)  # Shapely uses (x, y) = (lon, lat)

    # --- Combine all rows per sovereign country (cached after first call) --
    unified_4326, unified_proj = _load_unified_countries()

    # --- Inside India EEZ? (4326 is fine for containment) -----------------
    india_row = unified_4326[unified_4326["country"] == "India"]
    inside_india = not india_row.empty and india_row.geometry.iloc[0].contains(point_4326)

    # --- Reproject the query point for distance calculation ----------------
    point_proj = (
        gpd.GeoSeries([point_4326], crs="EPSG:4326")
        .to_crs(_METRIC_CRS)
        .iloc[0]
    )

    # --- Nearest EEZ *boundary line* ----------------------------------------
    # IMPORTANT: distance to the polygon itself is 0 for any point inside it
    # (the interior counts as part of the geometry), which makes it useless
    # for "how close am I to crossing a maritime border" warnings. Distance
    # to .boundary (the ring/line) gives the actual distance to the border,
    # whether the point is inside or outside that country's EEZ.
    distances_m = unified_proj.geometry.boundary.distance(point_proj)
    nearest_idx = distances_m.idxmin()
    nearest_country = unified_proj.loc[nearest_idx, "country"]
    nearest_distance_km = round(distances_m[nearest_idx] / 1000.0, 2)

    return {
        "location": {"latitude": lat, "longitude": lon},
        "inside_india_eez": inside_india,
        "nearest_eez_country": nearest_country,
        "distance_to_nearest_eez_boundary_km": nearest_distance_km,
        "source": "Marine Regions World EEZ v12",
        "crs": "EPSG:4326",
        "projection_used_for_distance": _METRIC_CRS,
        "restricted_zone_data_available": False,
    }


# ===================================================================
# FUNCTION 3 — Real PFZ / Ocean Conditions
# ===================================================================

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two lat/lon points."""
    earth_radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * earth_radius_km * math.asin(math.sqrt(a))


def _resample_to_sst_grid(
    sst_lats: np.ndarray,
    sst_lons: np.ndarray,
    src_lats: np.ndarray,
    src_lons: np.ndarray,
    src_data: np.ndarray,
) -> np.ndarray:
    """Nearest-neighbour resample *src_data* onto the SST lat/lon axes."""
    tgt_lat, tgt_lon = np.meshgrid(sst_lats, sst_lons, indexing="ij")
    resampled = np.empty(tgt_lat.shape, dtype=float)
    for i in range(tgt_lat.shape[0]):
        for j in range(tgt_lat.shape[1]):
            lat_idx = int(np.argmin(np.abs(src_lats - tgt_lat[i, j])))
            lon_idx = int(np.argmin(np.abs(src_lons - tgt_lon[i, j])))
            resampled[i, j] = src_data[lat_idx, lon_idx]
    return resampled


def _fetch_ocean_grid(lat: float, lon: float, radius_km: float) -> dict[str, Any] | None:
    """
    Fetch a small SST + chlorophyll grid around (lat, lon) from Copernicus Marine.
    Returns None if the grid cannot be retrieved (never fabricates values).
    """
    deg_pad = (radius_km * 1.6) / 111.0
    start = (
        datetime.now(timezone.utc) - timedelta(days=_cm._LOOKBACK_DAYS)
    ).strftime("%Y-%m-%d")

    try:
        sst_ds = copernicusmarine.open_dataset(
            dataset_id=_cm._SST_DATASET_ID,
            variables=[_cm._SST_VARIABLE],
            minimum_longitude=lon - deg_pad,
            maximum_longitude=lon + deg_pad,
            minimum_latitude=lat - deg_pad,
            maximum_latitude=lat + deg_pad,
            start_datetime=start,
        )
        chl_ds = copernicusmarine.open_dataset(
            dataset_id=_cm._CHL_DATASET_ID,
            variables=[_cm._CHL_VARIABLE],
            minimum_longitude=lon - deg_pad,
            maximum_longitude=lon + deg_pad,
            minimum_latitude=lat - deg_pad,
            maximum_latitude=lat + deg_pad,
            start_datetime=start,
        )
        if sst_ds is None or chl_ds is None:
            return None

        sst_slice = sst_ds[_cm._SST_VARIABLE].isel(time=-1)
        chl_slice = chl_ds[_cm._CHL_VARIABLE].isel(time=-1)

        sst_c = sst_slice.values.astype(float)
        if np.nanmean(sst_c) > 100:
            sst_c = sst_c - 273.15

        chl_lats = chl_slice["latitude"].values
        chl_lons = chl_slice["longitude"].values
        chl_values = chl_slice.values.astype(float)
        chl_on_sst = _resample_to_sst_grid(
            sst_slice["latitude"].values,
            sst_slice["longitude"].values,
            chl_lats,
            chl_lons,
            chl_values,
        )

        return {
            "lats": sst_slice["latitude"].values,
            "lons": sst_slice["longitude"].values,
            "sst_c": sst_c,
            "chl_mg_m3": chl_on_sst,
            "sst_time": str(sst_slice["time"].values),
            "chl_time": str(chl_slice["time"].values),
        }
    except Exception:
        return None


def _compute_suitability_zones(
    grid: dict[str, Any],
    center_lat: float,
    center_lon: float,
    radius_km: float,
    top_n: int = _TOP_N_ZONES,
) -> list[dict[str, Any]]:
    """
    Rank candidate AI-derived fishing zones from real SST + chlorophyll grids.
    Skips NaN chlorophyll pixels (cloud gaps) rather than inventing values.
    """
    lat_grid, lon_grid = np.meshgrid(grid["lats"], grid["lons"], indexing="ij")

    lat_spacing_km = 111.0 * abs(np.mean(np.diff(grid["lats"]))) if len(grid["lats"]) > 1 else 1.0
    mean_lat_rad = math.radians(center_lat)
    lon_spacing_km = (
        111.0 * math.cos(mean_lat_rad) * abs(np.mean(np.diff(grid["lons"])))
        if len(grid["lons"]) > 1 else 1.0
    )

    dsst_dy, dsst_dx = np.gradient(grid["sst_c"], lat_spacing_km, lon_spacing_km)
    gradient_c_per_km = np.sqrt(dsst_dx ** 2 + dsst_dy ** 2)

    chl_safe = np.clip(grid["chl_mg_m3"], 1e-3, None)
    log_chl = np.log(chl_safe)

    def _normalize(arr: np.ndarray) -> np.ndarray:
        finite = arr[np.isfinite(arr)]
        if finite.size == 0 or np.nanmax(finite) == np.nanmin(finite):
            return np.zeros_like(arr)
        return (arr - np.nanmin(finite)) / (np.nanmax(finite) - np.nanmin(finite))

    norm_gradient = _normalize(gradient_c_per_km)
    norm_chl = _normalize(log_chl)
    score = 0.5 * norm_gradient + 0.5 * norm_chl

    candidates: list[dict[str, Any]] = []
    it = np.nditer(score, flags=["multi_index"])
    for val in it:
        i, j = it.multi_index
        if not np.isfinite(val) or not np.isfinite(grid["chl_mg_m3"][i, j]):
            continue

        plat = float(lat_grid[i, j])
        plon = float(lon_grid[i, j])
        dist = _haversine_km(center_lat, center_lon, plat, plon)
        if dist > radius_km:
            continue

        is_front = gradient_c_per_km[i, j] >= _FRONT_GRADIENT_THRESHOLD_C_PER_KM
        is_high_chl = norm_chl[i, j] >= 0.6
        if is_front and is_high_chl:
            reason = "strong thermal front + elevated chlorophyll"
        elif is_front:
            reason = "thermal front present, moderate chlorophyll"
        elif is_high_chl:
            reason = "elevated chlorophyll, weak thermal front"
        else:
            reason = "baseline ocean conditions"

        candidates.append({
            "latitude": round(plat, 4),
            "longitude": round(plon, 4),
            "distance_km": round(dist, 2),
            "score": float(val),
            "reason": reason,
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)

    selected: list[dict[str, Any]] = []
    for cand in candidates:
        if len(selected) >= top_n:
            break
        too_close = any(
            _haversine_km(cand["latitude"], cand["longitude"], s["latitude"], s["longitude"])
            < _MIN_ZONE_SEPARATION_KM
            for s in selected
        )
        if not too_close:
            selected.append(cand)

    for zone in selected:
        zone.pop("score", None)
    return selected


def get_pfz_and_ocean_conditions(
    lat: float,
    lon: float,
    radius_km: float = 30.0,
) -> dict[str, Any]:
    """
    Return real ocean conditions and AI-derived potential fishing zones.

    Parameters
    ----------
    lat : float
        Latitude (-90 to 90).
    lon : float
        Longitude (-180 to 180).
    radius_km : float, optional
        Search radius in km for fishing-zone scoring (default 30).

    Returns
    -------
    dict
        Real SST, chlorophyll-a, and recommended fishing coordinates.
        Never fabricates measurements — missing values are returned as None.

    Data sources
    ------------
    • SST + chlorophyll point values: Copernicus Marine (via copernicus_ocean.py)
    • Fishing zones: derived from a local Copernicus SST/chlorophyll grid
    """
    _validate_lat_lon(lat, lon)
    if radius_km <= 0:
        raise ValueError(f"radius_km must be > 0, got {radius_km}")

    warnings: list[str] = []
    sources: list[str] = []

    sst_result = get_real_sst(lat, lon)
    sources.append(sst_result["source"])

    chl_search_km = min(radius_km, 25.0)
    chl_result = get_real_chlorophyll(lat, lon, search_radius_km=chl_search_km)
    if chl_result.get("source"):
        sources.append(chl_result["source"])
    if chl_result.get("note"):
        warnings.append(chl_result["note"])

    grid = _fetch_ocean_grid(lat, lon, radius_km)
    zones: list[dict[str, Any]] = []
    if grid is not None:
        zones = _compute_suitability_zones(grid, lat, lon, radius_km)
        if not zones:
            warnings.append(
                "Gridded data retrieved but no valid fishing-suitability candidates "
                "found within the search radius (likely chlorophyll cloud gaps)."
            )
    else:
        warnings.append(
            "Copernicus Marine grid unavailable — returning point SST/chlorophyll only; "
            "no fishing zones computed."
        )

    sst_c = sst_result["sst_celsius"]
    chlorophyll = chl_result.get("chlorophyll_mg_m3")

    if sst_c is None and chlorophyll is None:
        data_completeness = "none"
    elif zones and sst_c is not None:
        data_completeness = "full"
    else:
        data_completeness = "partial"

    return {
        "location": {"latitude": lat, "longitude": lon},
        "radius_km": radius_km,
        "sst_c": sst_c,
        "chlorophyll_mg_m3": chlorophyll,
        "sst_valid_time": sst_result.get("valid_time"),
        "chlorophyll_valid_time": chl_result.get("valid_time"),
        "chlorophyll_pixel": {
            "latitude": chl_result.get("pixel_latitude"),
            "longitude": chl_result.get("pixel_longitude"),
            "distance_from_query_km": chl_result.get("distance_from_query_km"),
        },
        "chlorophyll_temporal_resolution": chl_result.get("temporal_resolution"),
        "recommended_fishing_zones": zones,
        "data_completeness": data_completeness,
        "disclaimer": _PFZ_DISCLAIMER,
        "source": sources,
        "warnings": warnings,
        "is_mock_data": False,
    }
