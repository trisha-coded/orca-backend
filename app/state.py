"""
State definition for the ORCA multi-agent reasoning graph.
Maintains state across Supervisor, Domain Agents, Route Planner, Tides, Safety Gate, and Synthesizer.
"""

from typing import TypedDict, List, Dict, Any, Optional


class MarineAgentState(TypedDict, total=False):
    # Request Identifiers & Inputs
    request_id: str
    session_id: str
    latitude: float
    longitude: float
    location_name: Optional[str]
    query: str
    temporal_target: Optional[str]
    target_species: Optional[str]
    vessel_type: str
    language: str
    detected_language: str
    geocoding_meta: Optional[Dict[str, Any]]

    # Supervisor Node Outputs & Conditional Flags
    intent: str
    extracted_entities: Dict[str, Any]
    active_domains: List[str]
    requires_weather: bool
    requires_ocean: bool
    requires_geofence: bool
    requires_route: bool
    requires_tides: bool
    requires_temporal: bool

    # Domain Agent Outputs
    weather_data: Dict[str, Any]
    ocean_data: Dict[str, Any]
    geofence_data: Dict[str, Any]
    tides_data: Dict[str, Any]
    route_data: Dict[str, Any]

    # Safety Gate & Synthesizer Outputs
    safety_assessment: Dict[str, Any]
    advisory_text: str
    audio_broadcast_script: str
    explainability_chain: Dict[str, Any]
    geojson_features: List[Dict[str, Any]]

    # Pipeline Meta & Reasoning Logs
    reasoning_logs: List[Dict[str, Any]]
    cached: bool
    errors: List[str]
    start_time: float
