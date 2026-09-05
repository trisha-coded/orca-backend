"""
LangGraph Workflow Orchestrator for Oceanova marine intelligence pipeline.
Orchestrates: Supervisor -> Parallel Conditional Domain Agents (Weather, Ocean, Geofence, Tides, Routing) -> Synthesizer (Safety Gate, Explainability, VHF Script) -> Advisory JSON.
"""

import time
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.state import MarineAgentState
from app.schemas import (
    MarineAdvisoryRequest,
    MarineAdvisoryResponse,
    SafetyAssessment,
    WeatherCondition,
    OceanCondition,
    GeofenceCondition,
    TidalCondition,
    RouteOptimization,
    CycloneAlert,
    DepartureWindow,
    ExplainabilityChain,
    GeocodingInfo,
    AgentStepLog,
    GeoJSONFeatureCollection
)
from app.cache import cache
from app.tools.geocoding import geocoder
from app.agents.supervisor import supervisor_agent
from app.agents.domain_agents import domain_agents
from app.agents.synthesizer import synthesizer_agent
from app.limiter import workflow_semaphore


class MarineWorkflowOrchestrator:
    """
    Workflow Orchestrator coordinating Conversational NLU and the Multi-Agent Reasoning Layer.
    """

    async def run(self, request: MarineAdvisoryRequest) -> MarineAdvisoryResponse:
        t_start = time.time()
        req_id = str(uuid.uuid4())
        sess_id = request.session_id or f"sess_{uuid.uuid4().hex[:8]}"

        # 1. Pre-resolve coordinates from location or query if lat/lon not provided
        lat = request.latitude
        lon = request.longitude
        loc_name = request.location_name or getattr(request, "target_location", None)
        geo_match = None
        if (lat is None or lon is None) and loc_name:
            geo_match = geocoder.resolve_location(loc_name)
            if geo_match:
                lat = geo_match["latitude"]
                lon = geo_match["longitude"]
                request.latitude = lat
                request.longitude = lon
                request.location_name = geo_match["name"]
        elif (lat is None or lon is None) and request.query:
            geo_match = geocoder.resolve_location(request.query)
            if geo_match:
                lat = geo_match["latitude"]
                lon = geo_match["longitude"]
                request.latitude = lat
                request.longitude = lon
                request.location_name = geo_match["name"]

        effective_lang = supervisor_agent.detect_language(
            request.query or "",
            request.language or getattr(request, "preferred_language", None) or "en"
        )

        # 2. Quick Spatial Cache Check if lat/lon present
        if lat is not None and lon is not None:
            cache_key = cache.get_advisory_key(
                lat,
                lon,
                request.target_species,
                effective_lang
            )
            cached_data = await cache.get(cache_key)
            if cached_data:
                cached_data["request_id"] = req_id
                cached_data["session_id"] = sess_id
                cached_data["cached"] = True
                cached_data["execution_time_ms"] = round((time.time() - t_start) * 1000, 2)
                return MarineAdvisoryResponse(**cached_data)

        # 2. Concurrency-Controlled Graph Execution
        async with workflow_semaphore:
            # Initialize State
            state: MarineAgentState = {
                "request_id": req_id,
                "session_id": sess_id,
                "latitude": request.latitude,
                "longitude": request.longitude,
                "location_name": request.location_name,
                "query": request.query or "",
                "temporal_target": request.temporal_target,
                "target_species": request.target_species,
                "vessel_type": request.vessel_type or "Motorized Boat",
                "language": request.language or "en",
                "reasoning_logs": [],
                "errors": [],
                "start_time": t_start
            }

            # Node 1: Supervisor (Conversational NLU, Language Detection & Geocoding)
            supervisor_out = await supervisor_agent.execute(state)
            state.update(supervisor_out)
            all_logs = list(supervisor_out.get("reasoning_logs", []))

            # Node 2: Conditional Domain Agents (Parallel Weather, Ocean, Geofence, Tides, Routing)
            domain_out = await domain_agents.execute_conditional(state)
            state["weather_data"] = domain_out["weather_data"]
            state["ocean_data"] = domain_out["ocean_data"]
            state["geofence_data"] = domain_out["geofence_data"]
            state["tides_data"] = domain_out["tides_data"]
            state["route_data"] = domain_out["route_data"]
            all_logs.extend(domain_out.get("reasoning_logs", []))

            # Node 3: Synthesizer & Safety Gate (Explainability & VHF Radio Script)
            synth_out = await synthesizer_agent.execute(state)
            state["safety_assessment"] = synth_out["safety_assessment"]
            state["advisory_text"] = synth_out["advisory_text"]
            state["audio_broadcast_script"] = synth_out["audio_broadcast_script"]
            state["explainability_chain"] = synth_out["explainability_chain"]
            state["geojson_features"] = synth_out["geojson"].features
            all_logs.extend(synth_out.get("reasoning_logs", []))

        t_elapsed = round((time.time() - t_start) * 1000, 2)

        # 3. Construct Final Typed MarineAdvisoryResponse
        lat = state["latitude"]
        lon = state["longitude"]
        loc_name_val = state.get("location_name")
        if not loc_name_val:
            # Match against known port coordinates
            known_ports = [
                ("Mangalore", 12.9141, 74.8560), ("Cochin", 9.9312, 76.2673), ("Goa", 15.4056, 73.8043),
                ("Mumbai", 18.9220, 72.8347), ("Chennai", 13.0827, 80.2707), ("Visakhapatnam", 17.6868, 83.2185),
                ("Veraval", 20.9000, 70.3667), ("Porbandar", 21.6417, 69.6293), ("Paradip", 20.3167, 86.6167)
            ]
            for pname, plat, plon in known_ports:
                if abs(lat - plat) < 0.15 and abs(lon - plon) < 0.15:
                    loc_name_val = pname
                    break
        location_meta = {
            "latitude": lat,
            "longitude": lon,
            "location_name": loc_name_val or "Indian Coastal Waters",
            "coastal_region": self._identify_region(lat, lon)
        }

        # Sub-model construction
        weather_cond = WeatherCondition(**state["weather_data"]["condition"])
        ocean_cond = OceanCondition(**state["ocean_data"]["condition"])
        geofence_cond = GeofenceCondition(**state["geofence_data"]["condition"])
        safety_eval = SafetyAssessment(**state["safety_assessment"])

        # Optional enhanced models
        tides_cond = TidalCondition(**state["tides_data"]) if state.get("tides_data") else None

        route_opt = None
        if state.get("route_data"):
            rd = state["route_data"]
            route_opt = RouteOptimization(
                total_distance_nm=rd["total_distance_nm"],
                initial_bearing_deg=rd["initial_bearing_deg"],
                recommended_cruising_speed_knots=rd["recommended_cruising_speed_knots"],
                estimated_transit_time_hours=rd["estimated_transit_time_hours"],
                waypoints=rd.get("waypoints", []),
                summary=rd.get("summary", "")
            )

        cyclone_info = None
        if state.get("weather_data", {}).get("cyclone_assessment"):
            cyclone_info = CycloneAlert(**state["weather_data"]["cyclone_assessment"])

        departure_info = None
        if state.get("weather_data", {}).get("best_sailing_window"):
            departure_info = DepartureWindow(**state["weather_data"]["best_sailing_window"])

        explainability_info = None
        if state.get("explainability_chain"):
            explainability_info = ExplainabilityChain(**state["explainability_chain"])

        geocoding_info = None
        if state.get("geocoding_meta"):
            gm = state["geocoding_meta"]
            geocoding_info = GeocodingInfo(
                resolved_name=gm.get("name"),
                latitude=gm.get("latitude"),
                longitude=gm.get("longitude"),
                state=gm.get("state"),
                matched_by=gm.get("matched_by", "geocoder")
            )

        response = MarineAdvisoryResponse(
            request_id=req_id,
            session_id=sess_id,
            timestamp=datetime.now(timezone.utc),
            location=location_meta,
            target_species=state.get("target_species"),
            vessel_type=state.get("vessel_type", "Motorized Boat"),
            language=state.get("language", "en"),
            advisory_text=state["advisory_text"],
            audio_broadcast_script=state.get("audio_broadcast_script"),
            safety_assessment=safety_eval,
            weather_report=weather_cond,
            ocean_report=ocean_cond,
            geofence_report=geofence_cond,
            tides_report=tides_cond,
            route_plan=route_opt,
            cyclone_alert=cyclone_info,
            departure_window=departure_info,
            explainability=explainability_info,
            geocoding=geocoding_info,
            geojson=synth_out["geojson"],
            reasoning_logs=[AgentStepLog(**log) for log in all_logs],
            cached=False,
            execution_time_ms=t_elapsed
        )

        # 4. Save to Spatial Cache
        cache_key = cache.get_advisory_key(lat, lon, state.get("target_species"), state.get("language", "en"))
        await cache.set(cache_key, response.model_dump(), ttl_seconds=300)

        return response

    @staticmethod
    def _identify_region(lat: float, lon: float) -> str:
        """Infers Indian coastal water sector from coordinates."""
        if lon < 77.5:
            if lat > 18.0:
                return "North Arabian Sea (Gujarat / Maharashtra Coast)"
            elif lat > 14.0:
                return "Central Arabian Sea (Goa / Konkan Coast)"
            else:
                return "South Arabian Sea (Malabar / Kerala Coast)"
        elif lon > 91.0:
            return "Andaman & Nicobar Marine Basin"
        else:
            if lat < 11.0:
                return "Gulf of Mannar / Coromandel South Coast"
            elif lat < 16.0:
                return "Central Bay of Bengal (Tamil Nadu / Andhra Coast)"
            else:
                return "North Bay of Bengal (Odisha / West Bengal Coast)"


orchestrator = MarineWorkflowOrchestrator()
