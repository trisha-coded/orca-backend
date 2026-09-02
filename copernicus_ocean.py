"""
Copernicus Marine Data Layer — real SST + Chlorophyll-a
Smart India Hackathon 2026 — Agentic Marine Intelligence Platform

This module retrieves REAL (not simulated) gridded ocean data from the
Copernicus Marine Service:

  • Sea Surface Temperature (SST) — OSTIA L4 analysis
  • Chlorophyll-a concentration    — GlobColour multi-sensor L4 (gap-free)

Both datasets are queried with the `copernicusmarine` Python toolbox using
`open_dataset()`, which lazily opens the remote ARCO/Zarr store and only
pulls the small slice we actually ask for — no multi-GB downloads.

------------------------------------------------------------------------
SETUP (one-time, do this before running)
------------------------------------------------------------------------
1. Register (free, instant, no approval wait):
   https://data.marine.copernicus.eu/register

2. Install the toolbox:
   pip install copernicusmarine --break-system-packages

3. Log in once — this caches your credentials locally so you don't have
   to pass them on every call:
   copernicusmarine login

------------------------------------------------------------------------
DATASET IDS — how these were chosen
------------------------------------------------------------------------
SST:
  Product:   SST_GLO_SST_L4_NRT_OBSERVATIONS_010_001 (OSTIA, near-real-time)
  Dataset:   METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2
  Variable:  analysed_sst   (Kelvin — this module converts to Celsius)
  Grid:      0.05° (~5 km), daily, gap-free

Chlorophyll:
  Product:   OCEANCOLOUR_GLO_BGC_L4_NRT_009_102 (GlobColour, near-real-time)
  Dataset:   cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D
  Variable:  CHL   (mg/m3)
  Grid:      4 km, daily, gap-free (space-time interpolated to remove
             cloud gaps — a plain satellite pass often has no usable
             pixel at a single point on a given day, which is why the
             gap-free product is used here instead of the raw L3)

If either ID has moved (Copernicus does rename/version datasets), run:
    copernicusmarine describe --contains "GLO-SST-L4-NRT"
    copernicusmarine describe --contains "plankton_nrt_l4-gapfree"
and update _SST_DATASET_ID / _CHL_DATASET_ID below.

------------------------------------------------------------------------
IMPORTANT — what "real" means here
------------------------------------------------------------------------
These are satellite-derived L4 (gap-filled, modelled) products, not a
thermometer reading. That's completely standard for oceanography and is
what INCOIS/MOSDAC also build on — but don't describe this as "in-situ
measured" in the PPT. "Satellite-derived, Copernicus Marine Service" is
the accurate description.

This module does NOT compute PFZ or fishing-suitability zones. It only
answers: "what is the real SST and chlorophyll at this point, right now."
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

import copernicusmarine
import numpy as np

_SST_DATASET_ID = "METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2"
_SST_VARIABLE = "analysed_sst"

_CHL_DATASET_ID = "cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D"
_CHL_MONTHLY_DATASET_ID = "cmems_obs-oc_glo_bgc-plankton_nrt_l4-multi-4km_P1M"
_CHL_VARIABLE = "CHL"

# These L4 products run a day or two behind "now" (satellite processing +
# gap-filling latency). Look back a small window and take the most recent
# time step actually present, rather than assuming today exists yet.
_LOOKBACK_DAYS = 5


def _validate_lat_lon(lat: float, lon: float) -> None:
    if not (-90 <= lat <= 90):
        raise ValueError(f"Latitude must be between -90 and 90, got {lat}")
    if not (-180 <= lon <= 180):
        raise ValueError(f"Longitude must be between -180 and 180, got {lon}")


def get_real_sst(lat: float, lon: float) -> dict[str, Any]:
    """
    Fetch the most recent real SST value at (lat, lon) from Copernicus
    Marine (OSTIA L4).

    Returns
    -------
    dict with keys: latitude, longitude, sst_celsius, valid_time, source
    """
    _validate_lat_lon(lat, lon)
    start = (datetime.now(timezone.utc) - timedelta(days=_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    ds = copernicusmarine.open_dataset(
        dataset_id=_SST_DATASET_ID,
        variables=[_SST_VARIABLE],
        minimum_longitude=lon,
        maximum_longitude=lon,
        minimum_latitude=lat,
        maximum_latitude=lat,
        start_datetime=start,
        coordinates_selection_method="nearest",
    )
    if ds is None:
        raise RuntimeError(
            "copernicusmarine.open_dataset() returned None for the SST dataset. "
            "This almost always means you're not logged in yet — run "
            "`copernicusmarine login` once from your terminal and try again."
        )

    # Take the last available time step in the window (most recent).
    point = ds[_SST_VARIABLE].isel(time=-1)
    sst_kelvin = float(point.values.item())
    sst_celsius = round(sst_kelvin - 273.15, 2)
    valid_time = str(point["time"].values)

    return {
        "latitude": lat,
        "longitude": lon,
        "sst_celsius": sst_celsius,
        "valid_time": valid_time,
        "source": f"Copernicus Marine — {_SST_DATASET_ID} ({_SST_VARIABLE})",
        "is_mock_data": False,
    }


def get_real_chlorophyll(
    lat: float,
    lon: float,
    search_radius_km: float = 25.0,
) -> dict[str, Any]:
    """
    Fetch real chlorophyll-a near (lat, lon) from Copernicus Marine.

    Why this isn't a single point lookup
    -------------------------------------
    Chlorophyll is a passive optical satellite product — the sensor needs
    an actual cloud-free view of the water. Near the coast (river outflow,
    turbid "Case 2" water) and during the SW monsoon (heavy cloud cover
    over the Arabian Sea, roughly June-September), a specific point on a
    specific day frequently has no valid retrieval, even in the "gap-free"
    product. This is a real, well-documented data gap, not a bug — SST
    (OSTIA) doesn't have this problem because it blends in-situ and
    infrared/microwave sources that see through cloud, which is why your
    SST query worked immediately while chlorophyll came back NaN.

    Strategy, in order:
      1. Search a small radius (default 25 km) around the point in the
         daily gap-free product and return the nearest valid pixel.
      2. If nothing in that radius has a value (whole area cloud-gapped),
         fall back to the monthly composite, which aggregates far more
         satellite passes and is much more likely to have a value —
         clearly labelled as monthly, not daily.
      3. If even that has nothing, return an honest "no data" result
         instead of fabricating a number.

    Returns
    -------
    dict with chlorophyll_mg_m3 (or None), the actual pixel queried,
    how far it was from the requested point, valid_time, source, and a
    human-readable note explaining any fallback that happened.
    """
    _validate_lat_lon(lat, lon)

    daily = _query_chlorophyll_nearest_valid(
        lat, lon, _CHL_DATASET_ID, search_radius_km, lookback_days=_LOOKBACK_DAYS,
    )
    if daily is not None:
        daily["note"] = (
            None if daily["distance_from_query_km"] < 5
            else f"Requested point had no valid retrieval; used the nearest "
                 f"cloud-free pixel, {daily['distance_from_query_km']:.1f} km away."
        )
        daily["temporal_resolution"] = "daily (gap-free interpolated)"
        return daily

    # Nothing valid anywhere in the search radius for the daily product —
    # likely a monsoon cloud-out over the whole area. Try the monthly one.
    monthly = _query_chlorophyll_nearest_valid(
        lat, lon, _CHL_MONTHLY_DATASET_ID, search_radius_km, lookback_days=60,
    )
    if monthly is not None:
        monthly["note"] = (
            f"No valid daily retrieval within {search_radius_km:.0f} km "
            "(likely monsoon cloud cover) — using the monthly composite instead."
        )
        monthly["temporal_resolution"] = "monthly composite"
        return monthly

    return {
        "latitude": lat,
        "longitude": lon,
        "chlorophyll_mg_m3": None,
        "pixel_latitude": None,
        "pixel_longitude": None,
        "distance_from_query_km": None,
        "valid_time": None,
        "temporal_resolution": None,
        "source": f"Copernicus Marine — no valid retrieval within {search_radius_km:.0f} km, daily or monthly",
        "is_mock_data": False,
        "note": (
            "No usable satellite chlorophyll observation for this area/date "
            "range. Likely persistent cloud cover or optically complex coastal "
            "water. This is a genuine data gap, not a bug — do not fabricate "
            "a value here."
        ),
    }


def _query_chlorophyll_nearest_valid(
    lat: float,
    lon: float,
    dataset_id: str,
    search_radius_km: float,
    lookback_days: int,
) -> dict[str, Any] | None:
    """
    Query `dataset_id` in a box of `search_radius_km` around (lat, lon),
    walk backwards through the available time steps (most recent first),
    and return the nearest non-NaN pixel's value + location as soon as one
    is found. Returns None if every pixel in the box is NaN at every time
    step in the lookback window.
    """
    deg_lat = search_radius_km / 111.0
    deg_lon = search_radius_km / (111.0 * math.cos(math.radians(lat)))
    start = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    ds = copernicusmarine.open_dataset(
        dataset_id=dataset_id,
        variables=[_CHL_VARIABLE],
        minimum_longitude=lon - deg_lon,
        maximum_longitude=lon + deg_lon,
        minimum_latitude=lat - deg_lat,
        maximum_latitude=lat + deg_lat,
        start_datetime=start,
    )
    if ds is None:
        raise RuntimeError(
            f"copernicusmarine.open_dataset() returned None for {dataset_id}. "
            "This almost always means you're not logged in yet — run "
            "`copernicusmarine login` once from your terminal and try again."
        )

    da = ds[_CHL_VARIABLE]
    if "time" not in da.dims or da.sizes.get("time", 0) == 0:
        return None

    for t_idx in range(da.sizes["time"] - 1, -1, -1):
        time_slice = da.isel(time=t_idx)
        values = time_slice.values  # 2D array: (latitude, longitude)
        mask = ~np.isnan(values)
        if not mask.any():
            continue  # every pixel cloud-gapped at this time step, try an earlier one

        lat_vals = time_slice["latitude"].values
        lon_vals = time_slice["longitude"].values
        lon_grid, lat_grid = np.meshgrid(lon_vals, lat_vals)

        # Equirectangular approximation — fine at this scale (tens of km).
        dlat_km = (lat_grid - lat) * 111.0
        dlon_km = (lon_grid - lon) * 111.0 * math.cos(math.radians(lat))
        dist_km = np.sqrt(dlat_km**2 + dlon_km**2)
        dist_km_masked = np.where(mask, dist_km, np.inf)

        idx = np.unravel_index(np.argmin(dist_km_masked), dist_km_masked.shape)
        return {
            "latitude": lat,
            "longitude": lon,
            "chlorophyll_mg_m3": round(float(values[idx]), 3),
            "pixel_latitude": round(float(lat_grid[idx]), 4),
            "pixel_longitude": round(float(lon_grid[idx]), 4),
            "distance_from_query_km": round(float(dist_km_masked[idx]), 2),
            "valid_time": str(time_slice["time"].values),
            "source": f"Copernicus Marine — {dataset_id} ({_CHL_VARIABLE})",
            "is_mock_data": False,
        }

    return None  # every time step in the whole lookback window was fully NaN


if __name__ == "__main__":
    # Milestone check: Mangalore coordinates -> real SST -> real chlorophyll
    MANGALORE_LAT, MANGALORE_LON = 12.87, 74.84

    print(f"Querying Copernicus Marine for Mangalore ({MANGALORE_LAT}, {MANGALORE_LON})...")
    print()

    print("--- SST ---")
    sst_result = get_real_sst(MANGALORE_LAT, MANGALORE_LON)
    print(sst_result)
    print()

    print("--- Chlorophyll-a ---")
    chl_result = get_real_chlorophyll(MANGALORE_LAT, MANGALORE_LON)
    print(chl_result)
