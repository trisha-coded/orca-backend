from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class LanguageEnum(str, Enum):
    ENGLISH = "en"
    HINDI = "hi"
    TAMIL = "ta"
    TELUGU = "te"
    MALAYALAM = "ml"
    BENGALI = "bn"
    GUJARATI = "gu"
    MARATHI = "mr"
    ODIA = "or"


class VesselType(str, Enum):
    TRADITIONAL_CATAMARAN = "traditional_catamaran"
    MOTORIZED_CANOE = "motorized_canoe"
    MECHANIZED_TRAWLER = "mechanized_trawler"
    DEEP_SEA_LONGLINER = "deep_sea_longliner"
    COAST_GUARD_PATROL = "coast_guard_patrol"


class AlertLevel(str, Enum):
    GREEN = "GREEN"      # Safe conditions
    YELLOW = "YELLOW"    # Exercise caution
    ORANGE = "ORANGE"    # Hazardous - small crafts avoid
    RED = "RED"          # Extreme hazard / Prohibited zone


class GeofenceBufferAlert(str, Enum):
    SAFE = "SAFE"
    WARNING = "WARNING"
    CRITICAL_PROXIMITY = "CRITICAL_PROXIMITY"
    BREACH = "BREACH"


class Coordinates(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    timestamp: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    accuracy_m: Optional[float] = 10.0


class VesselContext(BaseModel):
    vessel_type: VesselType = VesselType.MECHANIZED_TRAWLER
    vessel_id: Optional[str] = "IND-TN-08-MM-1024"
    length_m: Optional[float] = 12.5
    engine_hp: Optional[float] = 120.0
    fuel_range_nm: Optional[float] = 60.0
    max_safe_wave_m: Optional[float] = 3.0
    max_safe_wind_knots: Optional[float] = 25.0


class GeoJSONGeometry(BaseModel):
    type: str = "Point"
    coordinates: Any


class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: Dict[str, Any] = Field(default_factory=dict)


class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature] = Field(default_factory=list)


class WeatherAssessment(BaseModel):
    wind_speed_knots: float
    wind_direction_deg: float
    gust_knots: float
    wave_height_m: float
    swell_period_s: float
    sea_state_code: int = Field(..., ge=0, le=9, description="WMO Sea State Code 0-9")
    sea_state_description: str
    precipitation_mm: float
    cyclonic_risk_score: float = Field(..., ge=0.0, le=1.0)
    is_safe: bool = True
    advisory_notes: List[str] = Field(default_factory=list)


class OceanAssessment(BaseModel):
    sst_celsius: Optional[float] = None
    chlorophyll_mg_m3: Optional[float] = None
    salinity_psu: Optional[float] = 34.5
    current_speed_knots: Optional[float] = 1.2
    current_direction_deg: Optional[float] = 180.0
    pfz_detected: bool = False
    pfz_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    target_species_recommendations: List[str] = Field(default_factory=list)
    recommended_fishing_zones: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    thermal_front_detected: bool = False
    upwelling_favorable: bool = False
    sst_valid_time: Optional[str] = None
    chlorophyll_valid_time: Optional[str] = None
    data_completeness: Optional[str] = "partial"
    disclaimer: Optional[str] = None
    is_mock_data: bool = False


class GeofenceAssessment(BaseModel):
    nearest_imbl_name: str
    distance_to_imbl_nm: float
    inside_indian_eez: bool = True
    inside_mpa: bool = False
    mpa_name: Optional[str] = None
    buffer_alert_level: GeofenceBufferAlert = GeofenceBufferAlert.SAFE
    is_boundary_breach: bool = False
    advisory_warning: Optional[str] = None
    geojson_features: Optional[List[Dict[str, Any]]] = None


class SafetyStatus(BaseModel):
    is_safe_to_sail: bool
    override_triggered: bool = False
    override_reasons: List[str] = Field(default_factory=list)
    alert_level: AlertLevel = AlertLevel.GREEN
    enforcement_action: str = "PROCEED_WITH_NORMAL_NAVIGATION"


class AuditLogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent: str
    stage: str
    action: str
    details: Dict[str, Any] = Field(default_factory=dict)


class MarineQueryRequest(BaseModel):
    query: str = Field(..., description="Natural language query from fisher/operator")
    coordinates: Coordinates
    vessel_context: Optional[VesselContext] = Field(default_factory=VesselContext)
    language: LanguageEnum = LanguageEnum.ENGLISH
    target_species: Optional[str] = None


class MarineAdvisoryResponse(BaseModel):
    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    language: LanguageEnum
    query: str
    safety_status: SafetyStatus
    advisory_title: str
    advisory_body: str
    audio_broadcast_script: str
    recommended_heading_deg: Optional[float] = None
    recommended_speed_knots: Optional[float] = None
    weather: WeatherAssessment
    ocean: OceanAssessment
    geofence: GeofenceAssessment
    spatial_features: GeoJSONFeatureCollection
    audit_trail: List[AuditLogEntry] = Field(default_factory=list)
