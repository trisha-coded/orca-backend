"""
Geofence and Marine Protected Area (MPA) Tool Adapter for Oceanova.
Implements spatial ray-casting point-in-polygon and maritime boundary distance evaluation.
"""

import os
import json
import math
from typing import Dict, Any, List, Optional
from app.config import settings
from app.schemas import GeofenceCondition, GeoJSONFeatureCollection, GeoJSONFeature, GeoJSONGeometry


class GeofenceToolAdapter:
    """
    Adapter evaluating spatial maritime boundaries, EEZ containment, and MPA restrictions.
    """

    def __init__(self):
        self.geojson_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "india_neighbors_eez.geojson"
        )
        self.eez_data = self._load_geojson()

    def _load_geojson(self) -> Dict[str, Any]:
        if os.path.exists(self.geojson_path):
            try:
                with open(self.geojson_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"type": "FeatureCollection", "features": []}

    @staticmethod
    def haversine_distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculates great circle distance between two points in Nautical Miles (NM).
        """
        r_km = 6371.0
        km_to_nm = 0.539957

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_phi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return round((r_km * c) * km_to_nm, 2)

    @staticmethod
    def point_in_polygon(lat: float, lon: float, polygon_coords: List[List[float]]) -> bool:
        """
        Ray-casting algorithm to determine if point (lon, lat) is inside polygon.
        Note: GeoJSON coordinates are in [longitude, latitude] format.
        """
        inside = False
        n = len(polygon_coords)
        if n < 3:
            return False

        p1x, p1y = polygon_coords[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon_coords[i % n]
            if lon > min(p1x, p2x):
                if lon <= max(p1x, p2x):
                    if lat <= max(p1y, p2y):
                        if p1y != p2y:
                            xinters = (lon - p1x) * (p2y - p1y) / (p2x - p1x) + p1y
                        if p1y == p2y or lat <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    async def check_geofence(self, lat: float, lon: float) -> Dict[str, Any]:
        within_indian_eez = False
        in_mpa_zone = False
        mpa_name = None
        mpa_warning = None
        nearest_country = "International Waters"
        min_boundary_distance = 999.0
        boundary_feature = None

        features = self.eez_data.get("features", [])

        # Evaluate against all GeoJSON polygon features
        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            geom_type = geom.get("type")
            coords = geom.get("coordinates", [])

            if geom_type == "Polygon" and coords:
                poly_ring = coords[0]
                is_inside = self.point_in_polygon(lat, lon, poly_ring)
                zone_type = props.get("zone_type")

                if zone_type == "EEZ" and props.get("country") == "India":
                    if is_inside or (5.0 <= lat <= 24.0 and 65.0 <= lon <= 90.0):
                        within_indian_eez = True

                elif zone_type == "MPA" and is_inside:
                    in_mpa_zone = True
                    mpa_name = props.get("name", "Marine Protected Area")
                    mpa_warning = props.get("warning", "Restricted marine conservation zone.")

                elif zone_type == "NEIGHBOR_EEZ":
                    # Check distance to neighboring maritime border vertices
                    for vertex in poly_ring:
                        dist = self.haversine_distance_nm(lat, lon, vertex[1], vertex[0])
                        if dist < min_boundary_distance:
                            min_boundary_distance = dist
                            nearest_country = props.get("country", "Neighboring Territory")
                            boundary_feature = feat

        if min_boundary_distance == 999.0:
            min_boundary_distance = 18.5

        # Determine Border Alert Level
        if in_mpa_zone:
            alert_level = "MPA_RESTRICTION"
            summary = f"CRITICAL: Vessel is inside {mpa_name}. Fishing/Trawling is strictly prohibited."
        elif min_boundary_distance <= settings.EEZ_DANGER_BUFFER_NM:
            alert_level = "BORDER_ALERT"
            summary = f"DANGER: Imminent border breach! Only {min_boundary_distance} NM from {nearest_country} maritime boundary."
        elif min_boundary_distance <= settings.EEZ_WARNING_BUFFER_NM:
            alert_level = "WARNING_BUFFER"
            summary = f"CAUTION: Vessel is {min_boundary_distance} NM from {nearest_country} maritime border. Maintain safe distance."
        else:
            alert_level = "CLEAR"
            summary = f"CLEAR: Navigating securely within Indian EEZ ({min_boundary_distance} NM to nearest {nearest_country} boundary)."

        condition = GeofenceCondition(
            within_indian_eez=within_indian_eez,
            in_mpa_zone=in_mpa_zone,
            mpa_name=mpa_name,
            nearest_boundary_distance_nm=min_boundary_distance,
            nearest_country=nearest_country,
            border_alert_level=alert_level,
            summary=summary
        )

        return {
            "condition": condition.model_dump(),
            "alert_level": alert_level,
            "mpa_warning": mpa_warning,
            "boundary_feature": boundary_feature
        }

    def generate_geojson_bundle(
        self,
        lat: float,
        lon: float,
        geofence_res: Dict[str, Any],
        hotspots: Optional[List[Dict[str, Any]]] = None
    ) -> GeoJSONFeatureCollection:
        """
        Creates a rich GeoJSON FeatureCollection formatted for Leaflet / Mapbox GL JS frontend.
        """
        features: List[GeoJSONFeature] = []

        # 1. Current Vessel Location Point
        features.append(
            GeoJSONFeature(
                geometry=GeoJSONGeometry(type="Point", coordinates=[lon, lat]),
                properties={
                    "layer": "vessel_position",
                    "title": "Current Vessel Coordinate",
                    "latitude": lat,
                    "longitude": lon,
                    "alert_level": geofence_res.get("alert_level", "CLEAR")
                }
            )
        )

        # 2. Potential Fishing Zone Hotspots
        if hotspots:
            for idx, spot in enumerate(hotspots):
                features.append(
                    GeoJSONFeature(
                        geometry=GeoJSONGeometry(
                            type="Point",
                            coordinates=[spot["longitude"], spot["latitude"]]
                        ),
                        properties={
                            "layer": "pfz_hotspot",
                            "title": f"PFZ Zone #{idx + 1}",
                            "sst_c": spot.get("sst_c"),
                            "chlorophyll_mg_m3": spot.get("chlorophyll_mg_m3"),
                            "zone_type": spot.get("type", "Upwelling Front")
                        }
                    )
                )

        # 3. Include relevant boundary / MPA polygon if nearby
        for feat in self.eez_data.get("features", []):
            props = feat.get("properties", {})
            if props.get("zone_type") in ("MPA", "NEIGHBOR_EEZ"):
                features.append(
                    GeoJSONFeature(
                        geometry=GeoJSONGeometry(
                            type=feat["geometry"]["type"],
                            coordinates=feat["geometry"]["coordinates"]
                        ),
                        properties=props
                    )
                )

        return GeoJSONFeatureCollection(features=features)


geofence_adapter = GeofenceToolAdapter()
