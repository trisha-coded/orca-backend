from typing import Any, Dict, List, Optional, TypedDict
from datetime import datetime


class MarineAgentState(TypedDict, total=False):
    """LangGraph agent execution state for Marine Intelligence Platform."""

    # Input Query & Metadata
    request_id: str
    query: str
    coordinates: Dict[str, Any]
    vessel_context: Dict[str, Any]
    language: str
    target_species: Optional[str]

    # Intent Parsing (Supervisor)
    parsed_intent: Dict[str, Any]
    requires_weather: bool
    requires_ocean: bool
    requires_geofence: bool

    # Domain Tool Outputs
    weather_data: Dict[str, Any]
    ocean_data: Dict[str, Any]
    geofence_data: Dict[str, Any]

    # Deterministic Safety Override Evaluation
    safety_eval: Dict[str, Any]
    override_triggered: bool
    alert_level: str

    # Advisory Synthesis
    advisory_title: str
    advisory_body: str
    audio_broadcast_script: str
    recommended_heading_deg: Optional[float]
    recommended_speed_knots: Optional[float]

    # Geospatial Output (GeoJSON)
    spatial_features: Dict[str, Any]

    # Audit Trail & Error Logs
    audit_trail: List[Dict[str, Any]]
    errors: List[str]
