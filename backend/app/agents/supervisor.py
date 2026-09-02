import re
import uuid
from typing import Any, Dict
from datetime import datetime, timezone
from app.state import MarineAgentState


def supervisor_intent_parser(state: MarineAgentState) -> MarineAgentState:
    """
    Supervisor Agent: Decomposes natural language queries, extracts entities,
    and routes control flow to relevant domain agents.
    """
    query = state.get("query", "").lower()
    coords = state.get("coordinates", {})
    vessel = state.get("vessel_context", {})

    # Default all domain tools to True for comprehensive marine advisory unless strictly targeted
    requires_weather = True
    requires_ocean = True
    requires_geofence = True

    # Detect specific target species in query
    species_patterns = {
        "tuna": "Yellowfin Tuna",
        "sardine": "Indian Oil Sardine",
        "mackerel": "Indian Mackerel",
        "prawn": "Tiger Prawns",
        "shrimp": "Prawns/Shrimp",
        "seer": "King Seer Fish",
        "surmai": "King Seer Fish / Surmai",
        "hilsa": "Hilsa Shad",
        "pomfret": "Silver/Black Pomfret",
    }
    extracted_species = state.get("target_species")
    for keyword, sp_name in species_patterns.items():
        if keyword in query:
            extracted_species = sp_name
            break

    # Intent classification
    intent_type = "GENERAL_MARINE_ADVISORY"
    if any(w in query for w in ["fish", "pfz", "catch", "shoal", "tuna", "sardine", "mackerel"]):
        intent_type = "FISHING_ZONE_OPTIMIZATION"
    elif any(w in query for w in ["weather", "storm", "cyclone", "wind", "wave", "rain", "sea state"]):
        intent_type = "METEOROLOGICAL_SAFETY"
    elif any(w in query for w in ["border", "boundary", "sri lanka", "pakistan", "imbl", "geofence", "safe to cross"]):
        intent_type = "BORDER_SECURITY_AND_GEOFENCE"
    elif any(w in query for w in ["sos", "danger", "emergency", "mayday", "sinking", "engine failure"]):
        intent_type = "EMERGENCY_MARITIME_ALERT"

    parsed_intent = {
        "intent_type": intent_type,
        "extracted_species": extracted_species,
        "query_tokens": re.findall(r"\w+", query),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Record supervisor audit step
    audit_trail = list(state.get("audit_trail", []))
    audit_trail.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "SupervisorAgent",
        "stage": "intent_parsing",
        "action": "DECOMPOSE_INTENT_AND_ROUTE",
        "details": {
            "intent_type": intent_type,
            "target_species": extracted_species,
            "routing": {
                "weather": requires_weather,
                "ocean": requires_ocean,
                "geofence": requires_geofence,
            },
        },
    })

    return {
        **state,
        "request_id": state.get("request_id") or f"req-{uuid.uuid4().hex[:8]}",
        "parsed_intent": parsed_intent,
        "target_species": extracted_species,
        "requires_weather": requires_weather,
        "requires_ocean": requires_ocean,
        "requires_geofence": requires_geofence,
        "audit_trail": audit_trail,
    }
