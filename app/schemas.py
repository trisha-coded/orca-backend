"""
Pydantic v2 schemas and GeoJSON models for the Oceanova backend.
Defines contracts for Client, Frontend, Swagger UI, Conversational Chat, and Multi-Agent Reasoning nodes.
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, model_validator
from datetime import datetime, timezone


# ==========================================
# GeoJSON Schemas (RFC 7946 Compliant)
# ==========================================

class GeoJSONGeometry(BaseModel):
    type: str = Field(..., description="Geometry type: Point, LineString, Polygon, MultiPolygon", examples=["Point"])
    coordinates: Any = Field(..., description="Coordinates array according to GeoJSON RFC 7946", examples=[[76.2673, 9.9312]])


class GeoJSONFeature(BaseModel):
    type: str = Field(default="Feature", description="GeoJSON object type", examples=["Feature"])
    geometry: GeoJSONGeometry = Field(..., description="Geometry definition")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Feature attributes (layer, title, alert_level, distance, etc.)")


class GeoJSONFeatureCollection(BaseModel):
    type: str = Field(default="FeatureCollection", description="GeoJSON collection type", examples=["FeatureCollection"])
    features: List[GeoJSONFeature] = Field(default_factory=list, description="List of GeoJSON spatial features")


# ==========================================
# Client Request Schemas
# ==========================================

class MarineAdvisoryRequest(BaseModel):
    latitude: Optional[float] = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="Latitude in decimal degrees (-90.0 to +90.0). Optional if location_name is provided or mentioned in query.",
        examples=[9.9312]
    )
    longitude: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Longitude in decimal degrees (-180.0 to +180.0). Optional if location_name is provided or mentioned in query.",
        examples=[76.2673]
    )
    location_name: Optional[str] = Field(
        default=None,
        description="Optional coastal port, city, or harbor name (e.g. Mangalore, Cochin, Rameswaram, Veraval, Vizag)",
        examples=["Mangalore"]
    )
    query: Optional[str] = Field(
        default="Is it safe to go fishing for Yellowfin Tuna today?",
        description="Natural language query from mariner or fisherman in English or regional language",
        examples=["Can I go fishing for Yellowfin Tuna near Mangalore tomorrow morning?"]
    )
    temporal_target: Optional[str] = Field(
        default=None,
        description="Optional time expression (e.g., 'tomorrow morning', 'next 2 days', 'today evening')",
        examples=["tomorrow morning"]
    )
    target_species: Optional[str] = Field(
        default=None,
        description="Targeted marine species (e.g., Yellowfin Tuna, Sardine, Mackerel, Hilsa, Prawns)",
        examples=["Yellowfin Tuna"]
    )
    vessel_type: Optional[str] = Field(
        default="Motorized Boat",
        description="Vessel category: Traditional Canoe, Motorized Boat, Mechanized Trawler, Deep Sea Vessel",
        examples=["Motorized Boat"]
    )
    language: Optional[str] = Field(
        default="en",
        description="Language code for synthesized advisory: en (English), ta (Tamil), ml (Malayalam), hi (Hindi), te (Telugu), or auto",
        examples=["en"]
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session ID for multi-turn conversational dialogue and context tracking",
        examples=["sess_cochin_01"]
    )
    target_location: Optional[str] = Field(default=None, description="Alias for location_name")
    preferred_language: Optional[str] = Field(default=None, description="Alias for language")
    temporal_window: Optional[str] = Field(default=None, description="Alias for temporal_target")
    vessel_category: Optional[str] = Field(default=None, description="Alias for vessel_type")

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if not values.get("location_name") and values.get("target_location"):
                values["location_name"] = values["target_location"]
            if not values.get("language") and values.get("preferred_language"):
                values["language"] = values["preferred_language"]
            if not values.get("temporal_target") and values.get("temporal_window"):
                values["temporal_target"] = values["temporal_window"]
            if not values.get("vessel_type") and values.get("vessel_category"):
                values["vessel_type"] = values["vessel_category"]
        return values

    model_config = {
        "json_schema_extra": {
            "example": {
                "location_name": "Mangalore",
                "query": "Is it safe to go fishing for mackerel tomorrow morning?",
                "temporal_target": "tomorrow morning",
                "target_species": "Mackerel",
                "vessel_type": "Motorized Boat",
                "language": "en",
                "session_id": "sess_mangalore_01"
            }
        }
    }


class GeofenceCheckRequest(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees", examples=[9.15])
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees", examples=[79.25])
    vessel_type: Optional[str] = Field(default="Motorized Boat", description="Vessel type", examples=["Mechanized Trawler"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "latitude": 9.15,
                "longitude": 79.25,
                "vessel_type": "Mechanized Trawler"
            }
        }
    }


class WeatherCheckRequest(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees", examples=[13.0827])
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees", examples=[80.2707])

    model_config = {
        "json_schema_extra": {
            "example": {
                "latitude": 13.0827,
                "longitude": 80.2707
            }
        }
    }


class OceanCheckRequest(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees", examples=[17.6868])
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees", examples=[83.2185])
    target_species: Optional[str] = Field(default="Yellowfin Tuna", description="Target species for PFZ evaluation", examples=["Yellowfin Tuna"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "latitude": 17.6868,
                "longitude": 83.2185,
                "target_species": "Yellowfin Tuna"
            }
        }
    }


# ==========================================
# Domain Assessment Models
# ==========================================

class WeatherCondition(BaseModel):
    timestamp: Optional[str] = None
    wind_speed_knots: float = Field(..., description="Sustained wind speed in knots", examples=[12.5])
    wind_direction_deg: float = Field(..., description="Wind direction in degrees", examples=[240.0])
    wind_gust_knots: float = Field(..., description="Wind gust speed in knots", examples=[16.0])
    wave_height_m: float = Field(..., description="Significant wave height in meters", examples=[1.2])
    wave_period_s: float = Field(..., description="Wave period in seconds", examples=[6.5])
    wave_direction_deg: float = Field(..., description="Dominant wave direction in degrees", examples=[230.0])
    sea_surface_temp_c: Optional[float] = Field(None, description="Sea Surface Temperature in Celsius", examples=[28.4])
    precipitation_mm: float = Field(default=0.0, description="Precipitation rate in mm/h", examples=[0.0])
    visibility_km: float = Field(default=10.0, description="Atmospheric visibility in km", examples=[10.0])
    status: str = Field(..., description="Safety status: SAFE, CAUTION, DANGEROUS", examples=["SAFE"])
    summary: str = Field(..., description="Natural language weather summary", examples=["Wind: 12.5 kts, Waves: 1.2m. Status is SAFE."])


class OceanCondition(BaseModel):
    sea_surface_temperature_c: float = Field(..., description="Sea Surface Temperature (SST) in °C", examples=[28.5])
    chlorophyll_a_mg_m3: float = Field(..., description="Chlorophyll-a concentration in mg/m³", examples=[0.65])
    ocean_current_velocity_ms: float = Field(..., description="Surface current velocity in m/s", examples=[0.45])
    ocean_current_direction_deg: float = Field(..., description="Surface current direction in degrees", examples=[180.0])
    salinity_psu: Optional[float] = Field(35.0, description="Ocean salinity in PSU", examples=[35.0])
    pfz_potential_score: float = Field(..., ge=0.0, le=100.0, description="Potential Fishing Zone index (0-100)", examples=[85.0])
    pfz_rating: str = Field(..., description="Rating: HIGH, MODERATE, LOW", examples=["HIGH"])
    summary: str = Field(..., description="Oceanographic condition summary", examples=["SST: 28.5°C, Chlorophyll-a: 0.65 mg/m³ -> HIGH Potential (85/100)."])


class GeofenceCondition(BaseModel):
    within_indian_eez: bool = Field(..., description="True if coordinates are within the Indian Exclusive Economic Zone", examples=[True])
    in_mpa_zone: bool = Field(..., description="True if coordinates fall inside a restricted Marine Protected Area", examples=[False])
    mpa_name: Optional[str] = Field(None, description="Name of Marine Protected Area if inside restricted zone", examples=[None])
    nearest_boundary_distance_nm: float = Field(..., description="Distance to nearest international boundary line in Nautical Miles", examples=[45.2])
    nearest_country: str = Field(..., description="Nearest neighboring country border (e.g. Sri Lanka, Maldives, Pakistan)", examples=["Sri Lanka"])
    border_alert_level: str = Field(..., description="CLEAR, WARNING_BUFFER, BORDER_ALERT, MPA_RESTRICTION", examples=["CLEAR"])
    summary: str = Field(..., description="Maritime boundary compliance summary", examples=["CLEAR: Navigating securely within Indian EEZ (45.2 NM to nearest Sri Lanka boundary)."])


class TidalCondition(BaseModel):
    current_height_m: float = Field(..., description="Current water elevation above chart datum in meters", examples=[1.25])
    tidal_state: str = Field(..., description="FLOODING (Rising), EBBING (Falling), SLACK WATER", examples=["FLOODING (Rising Tide)"])
    regime: str = Field(..., description="Microtidal, Mesotidal, Macrotidal", examples=["Mesotidal (Semi-Diurnal)"])
    next_high_tide_utc: str = Field(..., description="ISO 8601 UTC timestamp of next High Tide", examples=["2026-09-02T22:30:00Z"])
    next_low_tide_utc: str = Field(..., description="ISO 8601 UTC timestamp of next Low Tide", examples=["2026-09-03T04:45:00Z"])
    summary: str = Field(..., description="Nautical tidal summary and fishing recommendation")


class RouteOptimization(BaseModel):
    total_distance_nm: float = Field(..., description="Total nautical distance to fishing zone in Nautical Miles", examples=[14.2])
    initial_bearing_deg: float = Field(..., description="Initial true compass heading in degrees (0-360)", examples=[248.5])
    recommended_cruising_speed_knots: float = Field(..., description="Recommended safe speed in knots", examples=[8.5])
    estimated_transit_time_hours: float = Field(..., description="Estimated transit time in hours", examples=[1.67])
    waypoints: List[Dict[str, Any]] = Field(default_factory=list, description="Ordered navigational waypoints avoiding MPAs & borders")
    summary: str = Field(..., description="Route summary with headings and ETA")


class CycloneAlert(BaseModel):
    cyclonic_risk_score: float = Field(..., description="Normalized depression score from 0.0 to 1.0", examples=[0.15])
    is_cyclone_alert: bool = Field(..., description="True if cyclonic depression alert is active", examples=[False])
    alert_severity: str = Field(..., description="EXTREME, SEVERE, MODERATE, MINOR", examples=["MINOR"])
    lightning_risk: str = Field(..., description="HIGH, MODERATE, LOW", examples=["LOW"])
    directive: str = Field(..., description="Emergency action directive for mariners")


class DepartureWindow(BaseModel):
    recommended_window: str = Field(..., description="Recommended time window for departure", examples=["05:30 AM - 10:30 AM"])
    avg_wave_m: float = Field(..., description="Average wave height during window", examples=[0.85])
    avg_wind_kts: float = Field(..., description="Average wind speed during window", examples=[10.2])
    advice: str = Field(..., description="Actionable departure advice based on hourly forecast trends")


class ExplainabilityChain(BaseModel):
    why_safe_or_unsafe: str = Field(..., description="Human-readable explanation of meteorological and boundary safety status")
    why_this_hotspot: str = Field(..., description="Oceanographic evidence explaining thermal front and chlorophyll biological productivity")
    why_this_route: str = Field(..., description="Navigational rationale explaining heading and MPA avoidance")
    risk_breakdown: Dict[str, Any] = Field(default_factory=dict, description="Transparent breakdown of safety score deductions")
    confidence_score: float = Field(..., description="Model and data telemetry confidence metric (0-100)", examples=[95.0])


class GeocodingInfo(BaseModel):
    resolved_name: Optional[str] = Field(None, description="Resolved geographic name", examples=["Mangalore"])
    latitude: float = Field(..., description="Resolved latitude", examples=[12.9141])
    longitude: float = Field(..., description="Resolved longitude", examples=[74.8560])
    state: Optional[str] = Field(None, description="State or territory", examples=["Karnataka"])
    matched_by: str = Field(..., description="Source of coordinate resolution", examples=["indian_coastal_ports_database"])


class SafetyAssessment(BaseModel):
    overall_safety_status: str = Field(..., description="Composite status: SAFE, CAUTION, DANGEROUS", examples=["SAFE"])
    safety_score: int = Field(..., ge=0, le=100, description="Safety index from 0 (extreme hazard) to 100 (optimal)", examples=[100])
    go_no_go_decision: str = Field(..., description="Definitive nautical directive: GO, GO_WITH_CAUTION, NO_GO", examples=["GO"])
    warnings: List[str] = Field(default_factory=list, description="List of immediate active hazards or alerts")
    safety_recommendations: List[str] = Field(default_factory=list, description="Actionable safety guidance for the mariner")


class AgentStepLog(BaseModel):
    agent_name: str = Field(..., description="Name of the executing reasoning agent / node", examples=["SupervisorAgent"])
    status: str = Field(..., description="Node execution outcome: SUCCESS, WARNING, ERROR", examples=["SUCCESS"])
    summary: str = Field(..., description="Summary of reasoning step or tool telemetry", examples=["Intent identified as 'FISHING_ADVISORY'. Target species: 'Yellowfin Tuna'."])
    latency_ms: float = Field(..., description="Node execution time in milliseconds", examples=[2.45])
    timestamp: str = Field(..., description="ISO 8601 execution timestamp", examples=["2026-09-02T19:00:00Z"])


# ==========================================
# Main Response Schemas
# ==========================================

class MarineAdvisoryResponse(BaseModel):
    request_id: str = Field(..., description="Unique request UUID", examples=["3b2e59d4-1a3b-4c28-98e7-814d2e859f12"])
    session_id: str = Field(..., description="Session identifier for multi-turn conversations", examples=["sess_marine_01"])
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of response generation"
    )
    location: Dict[str, Any] = Field(..., description="Location metadata (latitude, longitude, coastal sector, port name)")
    target_species: Optional[str] = Field(None, description="Identified or requested target species", examples=["Yellowfin Tuna"])
    vessel_type: str = Field(..., description="Vessel category evaluated", examples=["Motorized Boat"])
    language: str = Field(..., description="Language of synthesized advisory", examples=["en"])
    
    # Core synthesized output
    advisory_text: str = Field(..., description="Plain-language marine advisory synthesized for mariners")
    audio_broadcast_script: Optional[str] = Field(None, description="Formatted VHF radio broadcast transcript for maritime voice alerts")
    
    # Reasoning assessments
    safety_assessment: SafetyAssessment = Field(..., description="Composite deterministic safety gate evaluation")
    weather_report: WeatherCondition = Field(..., description="Evaluated meteorological and wave conditions")
    ocean_report: OceanCondition = Field(..., description="Oceanographic and Potential Fishing Zone (PFZ) assessment")
    geofence_report: GeofenceCondition = Field(..., description="Maritime boundary, EEZ, and MPA compliance status")
    
    # Enhanced SIH Deliverables
    tides_report: Optional[TidalCondition] = Field(None, description="Harmonic tidal state and next high/low tides")
    route_plan: Optional[RouteOptimization] = Field(None, description="Safest navigation track to PFZ with waypoints and bearing")
    cyclone_alert: Optional[CycloneAlert] = Field(None, description="Proactive cyclonic depression and lightning assessment")
    departure_window: Optional[DepartureWindow] = Field(None, description="Optimal departure window based on 24h hourly forecast")
    explainability: Optional[ExplainabilityChain] = Field(None, description="Human-readable explainability and supporting evidence chain")
    geocoding: Optional[GeocodingInfo] = Field(None, description="Location resolution details if geocoded from port name")
    
    # Map layers for Frontend / Leaflet / Mapbox
    geojson: GeoJSONFeatureCollection = Field(..., description="GeoJSON layers (vessel point, safe route LineString, waypoints, PFZ hotspots, EEZ boundary, MPAs)")
    
    # Reasoning trace & telemetry
    reasoning_logs: List[AgentStepLog] = Field(default_factory=list, description="Step-by-step multi-agent reasoning trace")
    cached: bool = Field(default=False, description="Whether response was served from spatial query cache", examples=[False])
    execution_time_ms: float = Field(..., description="Total pipeline latency in milliseconds", examples=[28.45])


class DirectToolResponse(BaseModel):
    status: str = Field(..., description="Tool status: SUCCESS or ERROR", examples=["SUCCESS"])
    data: Dict[str, Any] = Field(..., description="Evaluated tool data payload")
    execution_time_ms: float = Field(..., description="Execution latency in milliseconds", examples=[5.12])


class CacheStatsResponse(BaseModel):
    cache_enabled: bool = Field(..., description="Whether caching is enabled", examples=[True])
    backend: str = Field(..., description="Cache backend: redis or in-memory-fallback", examples=["in-memory-fallback"])
    hits: int = Field(..., description="Total cache hits", examples=[14])
    misses: int = Field(..., description="Total cache misses", examples=[3])
    hit_ratio_percent: float = Field(..., description="Cache hit ratio percentage", examples=[82.35])
    in_memory_keys_count: int = Field(..., description="Active in-memory cached entries", examples=[5])
    redis_connected: bool = Field(..., description="Redis connectivity status", examples=[False])


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall health status: healthy / degraded", examples=["healthy"])
    service: str = Field(..., description="Service name", examples=["Oceanova Marine Intelligence Backend"])
    version: str = Field(..., description="Service version", examples=["1.0.0"])
    redis_cache: str = Field(..., description="connected or in-memory-fallback", examples=["in-memory-fallback"])
    uptime_seconds: float = Field(..., description="Process uptime in seconds", examples=[128.4])
    modules: Dict[str, str] = Field(..., description="Status of internal agent and tool modules")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp", examples=["2026-09-02T19:00:00Z"])


class SystemInfoResponse(BaseModel):
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    status: str = Field(..., description="Operational status")
    docs_url: str = Field(..., description="Interactive Swagger UI URL")
    redoc_url: str = Field(..., description="ReDoc API documentation URL")
    client_app_url: str = Field(..., description="Interactive Frontend Client Dashboard URL")
    advisory_endpoint: str = Field(..., description="Core advisory API endpoint")
    timestamp: str = Field(..., description="Current server UTC timestamp")
