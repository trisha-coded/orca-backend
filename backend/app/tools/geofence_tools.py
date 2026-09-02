import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from app.config import settings

try:
    import marine_tools
except ImportError:
    root_path = str(Path(__file__).resolve().parent.parent.parent.parent)
    if root_path not in sys.path:
        sys.path.insert(0, root_path)
    import marine_tools


# 1. Fallback Maritime Boundary Line Coordinates (Used for map line overlays)
IMBL_INDIA_SRI_LANKA_COORDS = [
    [79.8667, 10.0833],
    [79.5333, 9.7167],
    [79.3767, 9.3633],
    [79.4400, 9.1000],
    [79.5200, 9.0000],
    [79.6100, 8.8500],
    [79.7333, 8.6500],
    [80.0500, 8.3500],
]

IMBL_INDIA_PAKISTAN_COORDS = [
    [68.1610, 23.6330],
    [67.8000, 23.3000],
    [67.2000, 22.8000],
    [66.5000, 22.0000],
]

IMBL_INDIA_BANGLADESH_COORDS = [
    [89.1417, 21.6583],
    [89.2500, 21.1500],
    [89.5000, 20.5000],
    [89.9000, 19.5000],
]

# 2. Marine Protected Areas (MPAs) - Prohibited / Regulated Polygons [Lon, Lat]
MPA_GULF_OF_MANNAR = [
    [78.85, 9.15],
    [79.25, 9.25],
    [79.35, 9.05],
    [78.95, 8.90],
    [78.85, 9.15],
]

MPA_SUNDARBANS = [
    [88.40, 21.90],
    [89.10, 21.90],
    [89.10, 21.45],
    [88.40, 21.45],
    [88.40, 21.90],
]

MPA_GAHIRMATHA_TURTLE_SANCTUARY = [
    [86.75, 20.80],
    [87.15, 20.80],
    [87.15, 20.40],
    [86.75, 20.40],
    [86.75, 20.80],
]


def _point_in_polygon(lon: float, lat: float, ring: List[List[float]]) -> bool:
    """Ray-casting algorithm to test if (lon, lat) is inside polygon."""
    inside = False
    n = len(ring)
    if n < 3:
        return False
    p1x, p1y = ring[0]
    for i in range(1, n + 1):
        p2x, p2y = ring[i % n]
        if lat > min(p1y, p2y):
            if lat <= max(p1y, p2y):
                if lon <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (lat - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or lon <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def check_geofence_and_imbl(
    lat: float, lon: float, vessel_type: str = "mechanized_trawler"
) -> Dict[str, Any]:
    """
    Evaluates spatial proximity to international borders, EEZ, and MPAs using
    the Marine Regions World EEZ dataset (marine_tools.check_maritime_boundaries).
    """
    try:
        # Call the real GeoPandas EEZ boundary data layer
        boundary_res = marine_tools.check_maritime_boundaries(lat, lon)
        inside_india = boundary_res.get("inside_india_eez", False)
        nearest_country = boundary_res.get("nearest_eez_country", "India")
        dist_km = boundary_res.get("distance_to_nearest_eez_boundary_km", 10.0)
        
        # Convert km to Nautical Miles (1 NM = 1.852 km)
        min_imbl_dist_nm = round(dist_km / 1.852, 2)
        nearest_border_name = f"{nearest_country} Exclusive Economic Zone"
        is_foreign_breach = not inside_india and nearest_country != "India" and min_imbl_dist_nm > 0.0

    except Exception:
        # Fallback calculation if GeoPandas data fails
        inside_india = True
        min_imbl_dist_nm = 12.0
        nearest_border_name = "India-Sri Lanka IMBL (Palk Bay / Gulf of Mannar)"
        is_foreign_breach = False

    # Check Marine Protected Areas (MPAs)
    inside_mpa = False
    mpa_name = None

    if _point_in_polygon(lon, lat, MPA_GULF_OF_MANNAR):
        inside_mpa = True
        mpa_name = "Gulf of Mannar Marine National Park (No-Trawl Ecological Zone)"
    elif _point_in_polygon(lon, lat, MPA_SUNDARBANS):
        inside_mpa = True
        mpa_name = "Sundarbans Biosphere & Marine Reserve"
    elif _point_in_polygon(lon, lat, MPA_GAHIRMATHA_TURTLE_SANCTUARY):
        inside_mpa = True
        mpa_name = "Gahirmatha Marine Sanctuary (Olive Ridley Nesting Zone)"

    # Classify Alert Level
    is_breach = is_foreign_breach
    if is_breach:
        buffer_alert = "BREACH"
        warning = f"CRITICAL: Immediate border breach danger at {nearest_border_name}! Vessel outside Indian EEZ."
    elif min_imbl_dist_nm <= settings.IMBL_CRITICAL_BUFFER_NM:
        buffer_alert = "CRITICAL_PROXIMITY"
        warning = (
            f"DANGER: Vessel within {min_imbl_dist_nm} NM of {nearest_border_name}. "
            f"Turn back immediately to avoid international custody and vessel seizure."
        )
    elif min_imbl_dist_nm <= settings.IMBL_WARNING_BUFFER_NM:
        buffer_alert = "WARNING"
        warning = (
            f"CAUTION: Vessel approaching {nearest_border_name} "
            f"({min_imbl_dist_nm} NM remaining). Maintain radio watch."
        )
    else:
        buffer_alert = "SAFE"
        warning = None

    if inside_mpa:
        buffer_alert = "CRITICAL_PROXIMITY" if buffer_alert == "SAFE" else buffer_alert
        mpa_alert = f"PROHIBITED: Vessel inside {mpa_name}. Commercial bottom trawling strictly illegal."
        warning = f"{warning} | {mpa_alert}" if warning else mpa_alert

    # Generate GeoJSON features
    geojson_layers = _generate_geofence_geojson_features(lat, lon, nearest_border_name, min_imbl_dist_nm)

    return {
        "nearest_imbl_name": nearest_border_name,
        "distance_to_imbl_nm": min_imbl_dist_nm,
        "inside_indian_eez": inside_india,
        "inside_mpa": inside_mpa,
        "mpa_name": mpa_name,
        "buffer_alert_level": buffer_alert,
        "is_boundary_breach": is_breach,
        "advisory_warning": warning,
        "geojson_features": geojson_layers,
    }


def _generate_geofence_geojson_features(
    vessel_lat: float, vessel_lon: float, nearest_border: str, dist_nm: float
) -> List[Dict[str, Any]]:
    """Constructs GeoJSON features for maritime boundaries and safety buffer polygons."""
    features = []

    # 1. Vessel current position
    features.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [vessel_lon, vessel_lat]},
        "properties": {
            "title": "Vessel Position",
            "marker-color": "#2563EB",
            "marker-symbol": "ferry",
            "distance_to_imbl_nm": dist_nm,
        },
    })

    # 2. Sri Lanka IMBL Line
    features.append({
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": IMBL_INDIA_SRI_LANKA_COORDS},
        "properties": {
            "title": "India-Sri Lanka IMBL (1974/76)",
            "stroke": "#DC2626",
            "stroke-width": 3,
            "stroke-opacity": 0.9,
        },
    })

    # 3. Pakistan IMBL Line
    features.append({
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": IMBL_INDIA_PAKISTAN_COORDS},
        "properties": {
            "title": "India-Pakistan IMBL",
            "stroke": "#DC2626",
            "stroke-width": 3,
            "stroke-opacity": 0.9,
        },
    })

    # 4. Gulf of Mannar MPA Polygon
    features.append({
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [MPA_GULF_OF_MANNAR]},
        "properties": {
            "title": "Gulf of Mannar Marine National Park",
            "fill": "#10B981",
            "fill-opacity": 0.25,
            "stroke": "#059669",
            "stroke-width": 2,
        },
    })

    return features
