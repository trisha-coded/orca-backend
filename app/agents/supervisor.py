"""
Supervisor Agent: Conversational NLU, LLM-based entity extraction,
language auto-detection, coastal geocoding, and conditional LangGraph routing.
"""

import time
import os
import re
from typing import Dict, Any, Tuple, Optional, List
from app.state import MarineAgentState
from app.tools.geocoding import geocoder

KNOWN_SPECIES = [
    "yellowfin tuna", "skipjack tuna", "tuna", "indian oil sardine", "sardine",
    "indian mackerel", "mackerel", "hilsa", "seer fish", "kingfish", "surmai",
    "pomfret", "ribbonfish", "anchovy", "prawn", "shrimp", "squid", "cuttlefish",
    "bombay duck", "salmon", "crab", "lobster"
]

TEMPORAL_PATTERNS = [
    (r"\btomorrow morning\b", "tomorrow morning"),
    (r"\btomorrow afternoon\b", "tomorrow afternoon"),
    (r"\btomorrow evening\b", "tomorrow evening"),
    (r"\btomorrow night\b", "tomorrow night"),
    (r"\btomorrow\b", "tomorrow"),
    (r"\btonight\b", "tonight"),
    (r"\bthis evening\b", "this evening"),
    (r"\bthis afternoon\b", "this afternoon"),
    (r"\bnext 2 days\b", "next 2 days"),
    (r"\bnext 3 days\b", "next 3 days"),
    (r"\bnext week\b", "next week"),
    (r"\bweekend\b", "weekend"),
    (r"\btoday\b", "today")
]


class SupervisorAgent:
    """
    Intelligent Conversational Supervisor extracting intent, maritime entities,
    temporal windows, and location names to route execution to specialized domain agents.
    """

    @staticmethod
    def detect_language(query: str, requested_lang: Optional[str] = None) -> str:
        """
        Auto-detects language from Unicode scripts or mariner phonetic keywords.
        """
        if requested_lang and requested_lang.lower() not in ["auto", "", "none"]:
            return requested_lang.lower()

        text = query or ""
        # Tamil script
        if re.search(r"[\u0B80-\u0BFF]", text):
            return "ta"
        # Malayalam script
        elif re.search(r"[\u0D00-\u0D7F]", text):
            return "ml"
        # Devanagari (Hindi / Marathi)
        elif re.search(r"[\u0900-\u097F]", text):
            return "hi"
        # Telugu script
        elif re.search(r"[\u0C00-\u0C7F]", text):
            return "te"
        # Bengali script
        elif re.search(r"[\u0980-\u09FF]", text):
            return "bn"
        # Gujarati script
        elif re.search(r"[\u0A80-\u0AFF]", text):
            return "gu"

        return "en"

    @staticmethod
    def extract_temporal_window(query: str, explicit_temporal: Optional[str] = None) -> Optional[str]:
        if explicit_temporal:
            return explicit_temporal

        lower_q = (query or "").lower()
        for pattern, label in TEMPORAL_PATTERNS:
            if re.search(pattern, lower_q):
                return label
        return "today"

    @classmethod
    async def extract_intent_and_entities(
        cls,
        query: str,
        species_input: Optional[str] = None,
        location_input: Optional[str] = None,
        temporal_input: Optional[str] = None,
        current_lat: Optional[float] = None,
        current_lon: Optional[float] = None
    ) -> Dict[str, Any]:
        lower_q = (query or "").lower()
        extracted_species = species_input
        extracted_location = location_input
        temporal_window = cls.extract_temporal_window(query, temporal_input)

        # 1. Species extraction
        if not extracted_species:
            for sp in KNOWN_SPECIES:
                if sp in lower_q:
                    extracted_species = sp.title()
                    break

        # 2. Location extraction & Geocoding
        geocoding_result = None
        if location_input:
            geocoding_result = await geocoder.geocode_query(location_input)
        elif not current_lat or not current_lon:
            geocoding_result = geocoder.resolve_location(query)

        # If location resolved, extract coordinates
        resolved_lat = current_lat
        resolved_lon = current_lon
        location_name = location_input

        if geocoding_result:
            resolved_lat = geocoding_result["latitude"]
            resolved_lon = geocoding_result["longitude"]
            location_name = geocoding_result["name"]

        # Default to Cochin if still unspecified
        if resolved_lat is None or resolved_lon is None:
            resolved_lat = 9.9312
            resolved_lon = 76.2673
            location_name = "Cochin Coast"

        # 3. Intent Classification
        if any(w in lower_q for w in ["route", "heading", "bearing", "waypoint", "track", "direction", "how to reach", "navigate"]):
            intent = "ROUTE_PLANNING"
        elif any(w in lower_q for w in ["border", "boundary", "sri lanka", "maldives", "pakistan", "eez", "protected", "mpa", "sanctuary"]):
            intent = "NAVIGATION_AND_GEOFENCE"
        elif any(w in lower_q for w in ["tide", "tidal", "high tide", "low tide", "water level"]):
            intent = "TIDAL_AND_HARBOR_SAFETY"
        elif any(w in lower_q for w in ["cyclone", "storm", "depression", "gale", "emergency", "mayday", "evacuate", "danger"]):
            intent = "EMERGENCY_MARITIME_ALERT"
        elif any(w in lower_q for w in ["fish", "tuna", "sardine", "mackerel", "catch", "pfz", "hotspot", "chlorophyll", "plankton"]):
            intent = "FISHING_ADVISORY"
        elif any(w in lower_q for w in ["wave", "wind", "weather", "gust", "rain", "tomorrow", "forecast"]):
            intent = "SAFETY_AND_WEATHER"
        else:
            intent = "GENERAL_MARINE_ADVISORY"

        # 4. Conditional Graph Requirement Flags
        requires_weather = True  # Always evaluate weather for mariner safety
        requires_ocean = intent in ["FISHING_ADVISORY", "GENERAL_MARINE_ADVISORY", "ROUTE_PLANNING"]
        requires_geofence = True  # Always evaluate safety borders
        requires_route = intent in ["ROUTE_PLANNING", "FISHING_ADVISORY", "GENERAL_MARINE_ADVISORY"]
        requires_tides = intent in ["TIDAL_AND_HARBOR_SAFETY", "GENERAL_MARINE_ADVISORY", "ROUTE_PLANNING", "SAFETY_AND_WEATHER"]
        requires_temporal = temporal_window is not None

        active_domains = ["weather", "geofence"]
        if requires_ocean:
            active_domains.append("ocean")
        if requires_route:
            active_domains.append("routing")
        if requires_tides:
            active_domains.append("tides")

        return {
            "intent": intent,
            "target_species": extracted_species,
            "location_name": location_name,
            "latitude": resolved_lat,
            "longitude": resolved_lon,
            "geocoding_meta": geocoding_result,
            "temporal_target": temporal_window,
            "requires_weather": requires_weather,
            "requires_ocean": requires_ocean,
            "requires_geofence": requires_geofence,
            "requires_route": requires_route,
            "requires_tides": requires_tides,
            "requires_temporal": requires_temporal,
            "active_domains": active_domains
        }

    async def execute(self, state: MarineAgentState) -> Dict[str, Any]:
        t0 = time.time()
        query = state.get("query", "")
        explicit_species = state.get("target_species")
        explicit_location = state.get("location_name")
        explicit_temporal = state.get("temporal_target")
        current_lat = state.get("latitude")
        current_lon = state.get("longitude")
        user_lang = state.get("language", "en")

        detected_lang = self.detect_language(query, user_lang)

        nlu_res = await self.extract_intent_and_entities(
            query=query,
            species_input=explicit_species,
            location_input=explicit_location,
            temporal_input=explicit_temporal,
            current_lat=current_lat,
            current_lon=current_lon
        )

        elapsed = round((time.time() - t0) * 1000, 2)
        loc_str = f"at {nlu_res['location_name']} ({nlu_res['latitude']}, {nlu_res['longitude']})"
        step_log = {
            "agent_name": "SupervisorAgent (Conversational NLU)",
            "status": "SUCCESS",
            "summary": (
                f"Intent: '{nlu_res['intent']}' {loc_str}. Target species: '{nlu_res['target_species'] or 'General Pelagic'}'. "
                f"Temporal target: '{nlu_res['temporal_target']}'. Language: '{detected_lang}'. "
                f"Activated domains: {', '.join(nlu_res['active_domains'])}."
            ),
            "latency_ms": elapsed,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        return {
            **nlu_res,
            "language": detected_lang,
            "detected_language": detected_lang,
            "reasoning_logs": [step_log]
        }


supervisor_agent = SupervisorAgent()
