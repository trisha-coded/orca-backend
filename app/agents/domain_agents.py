"""
Domain Reasoning Agents: Weather, Ocean, Geofence, Tides, and Route Optimization Nodes.
Executes domain intelligence in parallel based on conditional NLU requirements.
"""

import time
import asyncio
from typing import Dict, Any, List
from app.state import MarineAgentState
from app.tools.weather_tools import weather_adapter
from app.tools.ocean_tools import ocean_adapter
from app.tools.geofence_tools import geofence_adapter
from app.tools.tides import tide_engine
from app.tools.routing import route_engine


class DomainAgents:
    """
    Executes domain-specific tools concurrently and conditionally populates MarineAgentState.
    """

    async def weather_node(self, state: MarineAgentState) -> Dict[str, Any]:
        t0 = time.time()
        lat = state["latitude"]
        lon = state["longitude"]
        temporal_target = state.get("temporal_target")

        weather_res = await weather_adapter.get_weather_assessment(lat, lon, temporal_target)
        elapsed = round((time.time() - t0) * 1000, 2)

        status = weather_res["status"]
        cond = weather_res["condition"]
        cyclone = weather_res.get("cyclone_assessment", {})
        window = weather_res.get("best_sailing_window", {})

        cyclone_tag = f" [Cyclone Risk: {cyclone.get('alert_severity', 'LOW')}]" if cyclone.get("is_cyclone_alert") else ""
        step_log = {
            "agent_name": "WeatherAgent",
            "status": "SUCCESS" if status != "DANGEROUS" else "WARNING",
            "summary": f"Weather evaluated: Wind {cond['wind_speed_knots']} kts, Waves {cond['wave_height_m']}m. Best window: {window.get('recommended_window')}. Condition is {status}{cyclone_tag}.",
            "latency_ms": elapsed,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        return {
            "weather_data": weather_res,
            "step_log": step_log
        }

    async def ocean_node(self, state: MarineAgentState) -> Dict[str, Any]:
        t0 = time.time()
        lat = state["latitude"]
        lon = state["longitude"]
        species = state.get("target_species")

        ocean_res = await ocean_adapter.get_ocean_assessment(lat, lon, species)
        elapsed = round((time.time() - t0) * 1000, 2)

        cond = ocean_res["condition"]
        step_log = {
            "agent_name": "OceanAgent",
            "status": "SUCCESS",
            "summary": f"Ocean physics evaluated: SST {cond['sea_surface_temperature_c']}°C, Chlorophyll {cond['chlorophyll_a_mg_m3']} mg/m³. PFZ rating is {ocean_res['pfz_rating']} ({ocean_res['pfz_score']}/100) with {len(ocean_res.get('hotspots', []))} active hotspots.",
            "latency_ms": elapsed,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        return {
            "ocean_data": ocean_res,
            "step_log": step_log
        }

    async def geofence_node(self, state: MarineAgentState) -> Dict[str, Any]:
        t0 = time.time()
        lat = state["latitude"]
        lon = state["longitude"]

        geofence_res = await geofence_adapter.check_geofence(lat, lon)
        elapsed = round((time.time() - t0) * 1000, 2)

        cond = geofence_res["condition"]
        step_log = {
            "agent_name": "GeofenceAgent",
            "status": "SUCCESS" if cond["border_alert_level"] == "CLEAR" else "WARNING",
            "summary": f"Geofence verified: Within EEZ={cond['within_indian_eez']}, Border Alert={cond['border_alert_level']}, Distance to {cond['nearest_country']}={cond['nearest_boundary_distance_nm']} NM.",
            "latency_ms": elapsed,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        return {
            "geofence_data": geofence_res,
            "step_log": step_log
        }

    async def tides_node(self, state: MarineAgentState) -> Dict[str, Any]:
        t0 = time.time()
        lat = state["latitude"]
        lon = state["longitude"]

        tide_res = tide_engine.compute_tide_assessment(lat, lon)
        elapsed = round((time.time() - t0) * 1000, 2)

        step_log = {
            "agent_name": "TidesAgent",
            "status": "SUCCESS",
            "summary": f"Tidal state: {tide_res['tidal_state']} (Height: {tide_res['current_height_m']}m). Next High Tide: {tide_res['next_high_tide_utc']}.",
            "latency_ms": elapsed,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        return {
            "tides_data": tide_res,
            "step_log": step_log
        }

    async def routing_node(self, state: MarineAgentState, target_hotspot: Dict[str, Any] = None) -> Dict[str, Any]:
        t0 = time.time()
        lat = state["latitude"]
        lon = state["longitude"]
        target_lat = target_hotspot.get("latitude") if target_hotspot else None
        target_lon = target_hotspot.get("longitude") if target_hotspot else None

        route_res = route_engine.plan_safest_route(lat, lon, target_lat, target_lon)
        elapsed = round((time.time() - t0) * 1000, 2)

        step_log = {
            "agent_name": "RoutingAgent",
            "status": "SUCCESS",
            "summary": f"Safest navigational track planned: Distance {route_res['total_distance_nm']} NM, Bearing {route_res['initial_bearing_deg']}° (ETA: {route_res['estimated_transit_time_hours']} hrs) with {len(route_res['waypoints'])} waypoints.",
            "latency_ms": elapsed,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        return {
            "route_data": route_res,
            "step_log": step_log
        }

    async def execute_conditional(self, state: MarineAgentState) -> Dict[str, Any]:
        """
        Conditionally and concurrently executes domain agents based on query requirements.
        """
        tasks = []
        task_names = []

        # Weather is always executed for nautical safety
        tasks.append(self.weather_node(state))
        task_names.append("weather")

        # Geofence is always executed for border security
        tasks.append(self.geofence_node(state))
        task_names.append("geofence")

        # Conditionally execute Oceanography
        if state.get("requires_ocean", True):
            tasks.append(self.ocean_node(state))
            task_names.append("ocean")

        # Conditionally execute Tides
        if state.get("requires_tides", True):
            tasks.append(self.tides_node(state))
            task_names.append("tides")

        results = await asyncio.gather(*tasks)

        out: Dict[str, Any] = {
            "weather_data": {},
            "ocean_data": {},
            "geofence_data": {},
            "tides_data": {},
            "route_data": {},
            "reasoning_logs": []
        }

        for name, res in zip(task_names, results):
            if name == "weather":
                out["weather_data"] = res["weather_data"]
            elif name == "geofence":
                out["geofence_data"] = res["geofence_data"]
            elif name == "ocean":
                out["ocean_data"] = res["ocean_data"]
            elif name == "tides":
                out["tides_data"] = res["tides_data"]
            out["reasoning_logs"].append(res["step_log"])

        # Execute Routing using primary PFZ hotspot if available
        if state.get("requires_route", True):
            hotspots = out["ocean_data"].get("hotspots", [])
            primary_hotspot = hotspots[0] if hotspots else None
            route_res = await self.routing_node(state, primary_hotspot)
            out["route_data"] = route_res["route_data"]
            out["reasoning_logs"].append(route_res["step_log"])

        return out

    async def execute_parallel(self, state: MarineAgentState) -> Dict[str, Any]:
        """Backward compatible execution wrapper."""
        return await self.execute_conditional(state)


domain_agents = DomainAgents()
