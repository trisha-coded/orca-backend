"""
Main FastAPI server for Oceanova Marine Intelligence Platform.
Entry point for Conversational Client, Frontend, Swagger UI (/docs), ReDoc (/redoc), and API consumers.
"""

import time
import os
import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, Request, status, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import settings
from app.schemas import (
    MarineAdvisoryRequest,
    MarineAdvisoryResponse,
    GeofenceCheckRequest,
    GeofenceCondition,
    WeatherCheckRequest,
    WeatherCondition,
    OceanCheckRequest,
    OceanCondition,
    TidalCondition,
    RouteOptimization,
    GeocodingInfo,
    CacheStatsResponse,
    HealthResponse,
    SystemInfoResponse
)
from app.graph import orchestrator
from app.limiter import rate_limit_dependency
from app.cache import cache
from app.tools.geofence_tools import geofence_adapter
from app.tools.weather_tools import weather_adapter
from app.tools.ocean_tools import ocean_adapter
from app.tools.tides import tide_engine
from app.tools.routing import route_engine
from app.tools.geocoding import geocoder
from app.tools.speech import synthesize_speech, process_speech_audio

# Service startup tracking
_service_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 Initializing {settings.PROJECT_NAME} v{settings.VERSION}...")
    print(f"📡 API Documentation available at: http://{settings.HOST}:{settings.PORT}/docs")
    print(f"🗺️ Interactive Client available at: http://{settings.HOST}:{settings.PORT}/client")

    async def _warmup_cache():
        try:
            from app.graph import orchestrator
            from app.schemas import MarineAdvisoryRequest
            warmup_ports = [
                ("Mangalore", 12.9141, 74.8560),
                ("Cochin", 9.9312, 76.2673),
                ("Mumbai", 18.9220, 72.8347),
                ("Goa", 15.4056, 73.8043),
                ("Chennai", 13.0827, 80.2707),
                ("Visakhapatnam", 17.6868, 83.2185),
            ]
            for port_name, lat, lon in warmup_ports:
                try:
                    req = MarineAdvisoryRequest(
                        query=f"Is it safe to fish near {port_name}?",
                        location_name=port_name,
                        latitude=lat,
                        longitude=lon,
                        preferred_language="en"
                    )
                    await orchestrator.run(req)
                except Exception:
                    pass
        except Exception:
            pass

    asyncio.create_task(_warmup_cache())
    yield
    print("🛑 Shutting down Oceanova Decision-Support Engine.")


app = FastAPI(
    title="🌊 Oceanova Marine Intelligence Platform - API",
    version=settings.VERSION,
    lifespan=lifespan,
    description=r"""
### 🌊 Autonomous Multi-Agent Marine Intelligence & Conversational Platform

The **Oceanova Platform** provides real-time marine meteorology, Copernicus oceanographic biological productivity analysis, Potential Fishing Zone (PFZ) modeling, spatial maritime boundary / Marine Protected Area (MPA) geofencing, safest nautical route optimization, and harmonic tidal predictions for Indian coastal waters.

---

### 🏛️ Architecture Overview
```
Client / Frontend / Swagger UI / Natural Language Voice
          │
          ▼  POST /api/v1/advisory
FastAPI Decision Engine (app/main.py)
          │
   LangGraph Orchestrator (app/graph.py)
     ├── Supervisor Agent (Conversational NLU, Language Auto-Detect, Coastal Geocoding)
     ├── Parallel Conditional Domain Agents:
     │     ├── Weather Agent (Wind, Waves, Temporal Trend, Cyclone Risk)
     │     ├── Ocean Agent (SST, Chlorophyll, PFZ Scoring & Hotspots)
     │     ├── Geofence Agent (IMBL Proximity & MPA Detection)
     │     ├── Tides Agent (Harmonic Astronomical Tides & Sea Level)
     │     └── Routing Agent (Safest Track Optimization Avoiding MPAs)
     └── Synthesizer Agent (Safety Gate + Multilingual Synthesis + Explainability + VHF Script)
          │
          ▼
MarineAdvisoryResponse (Plain-Language Advice + RFC 7946 GeoJSON + VHF Script + Route Waypoints + Tides)
```

---

### 🛡️ Deterministic Safety Rules
1. **IMBL Proximity (≤ 1.0 NM)**: Immediate border violation warning (`BORDER_ALERT` / `RED`).
2. **MPA Encroachment**: Bottom trawling / commercial fishing restriction enforced (`MPA_RESTRICTION` / `RED`).
3. **Severe Weather**: Wave height $\ge 2.5\text{m}$ or winds $\ge 25\text{ kts}$ trigger mandatory `NO_GO` directives.
4. **Safety Veto**: When `NO_GO` is triggered, economic PFZ recommendations are overridden to prioritize human safety.

---

### 🗣️ Supported Languages
- **English (`en`)** | **Tamil (`ta`)** | **Malayalam (`ml`)** | **Hindi (`hi`)** | **Telugu (`te`)**
    """,
    openapi_tags=[
        {
            "name": "Advisory & Conversational AI",
            "description": "Core multi-agent decision support pipeline with natural language geocoding (`/api/v1/advisory`)"
        },
        {
            "name": "Route Optimization",
            "description": "Nautical route planning avoiding MPAs and international boundary buffers"
        },
        {
            "name": "Tides & Harbor Safety",
            "description": "Harmonic tidal phase predictions, tidal heights, and high/low tide timestamps"
        },
        {
            "name": "Geofence & Boundaries",
            "description": "Maritime boundaries, Indian EEZ, and Marine Protected Area (MPA) spatial checks"
        },
        {
            "name": "Weather & Meteorology",
            "description": "Real-time marine weather, wind speeds, wave heights, best sailing window, and cyclone risk"
        },
        {
            "name": "Oceanography & PFZ",
            "description": "Sea surface temperature (SST), Chlorophyll-a, and Potential Fishing Zone modeling"
        },
        {
            "name": "Geocoding",
            "description": "Indian coastal ports, fishing harbors, and landing center coordinate resolution"
        },
        {
            "name": "Cache & Performance",
            "description": "Spatial query caching telemetry and cache invalidation"
        },
        {
            "name": "System & Telemetry",
            "description": "Liveness probes, service metadata, and readiness health checks"
        }
    ],
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS if isinstance(settings.ALLOWED_ORIGINS, list) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = round((time.time() - start_time) * 1000, 2)
    response.headers["X-Process-Time-Ms"] = str(process_time)
    return response


# ==========================================
# Root & Health Endpoints
# ==========================================

@app.get(
    "/",
    tags=["System & Telemetry"],
    summary="Service Discovery & Oceanova Marine Intelligence Platform",
    description="Returns root platform metadata for API consumers, or serves the interactive Oceanova frontend for web browsers."
)
async def root_info(request: Request):
    accept = request.headers.get("accept", "")
    client_html_path = os.path.join(os.path.dirname(__file__), "client", "index.html")
    if "text/html" in accept and os.path.exists(client_html_path):
        with open(client_html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    return SystemInfoResponse(
        service=settings.PROJECT_NAME,
        version=settings.VERSION,
        status="OPERATIONAL",
        docs_url="/docs",
        redoc_url="/redoc",
        client_app_url="/client",
        advisory_endpoint=f"{settings.API_V1_STR}/advisory",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System & Telemetry"],
    summary="Health & Readiness Probe",
    description="Returns service health, uptime, Redis spatial cache status, and module statuses."
)
@app.get(
    f"{settings.API_V1_STR}/health",
    response_model=HealthResponse,
    tags=["System & Telemetry"],
    summary="API v1 Health Probe"
)
async def health_check() -> HealthResponse:
    redis_connected = await cache.is_connected()
    uptime = round(time.time() - _service_start_time, 2)
    return HealthResponse(
        status="healthy",
        service=settings.PROJECT_NAME,
        version=settings.VERSION,
        redis_cache="connected" if redis_connected else "in-memory-fallback",
        uptime_seconds=uptime,
        modules={
            "supervisor_agent": "active",
            "weather_agent": "active",
            "ocean_agent": "active",
            "geofence_agent": "active",
            "tides_agent": "active",
            "routing_agent": "active",
            "synthesizer_agent": "active",
            "geocoding_engine": "active",
            "spatial_cache": "active",
            "rate_limiter": "active"
        },
        timestamp=datetime.now(timezone.utc).isoformat()
    )


# ==========================================
# Core Advisory & Conversational Gateway
# ==========================================

@app.post(
    f"{settings.API_V1_STR}/advisory",
    response_model=MarineAdvisoryResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_dependency)],
    tags=["Advisory & Conversational AI"],
    summary="Generate Marine & Fishing Advisory (Conversational NLU + Multi-Agent)",
    description="""
**Main Multi-Agent Decision Support Pipeline:**
- Accepts natural language text (e.g., *"Is it safe to fish near Mangalore tomorrow morning for mackerel?"*) OR explicit coordinates.
- **Supervisor Agent**: Auto-resolves location names (100+ Indian coastal ports), parses temporal windows, auto-detects language, and routes conditionally.
- **Parallel Domain Agents**: Weather (with hourly departure window and cyclone risk), Ocean (SST and PFZ), Geofence (EEZ/MPA), Tides, and Safest Route Optimization.
- **Synthesizer Safety Gate**: Applies deterministic safety overrides, generates explainable reasoning chain, VHF radio script, and unified RFC 7946 GeoJSON map layers.
    """
)
async def create_marine_advisory(request: MarineAdvisoryRequest) -> MarineAdvisoryResponse:
    try:
        advisory_response = await orchestrator.run(request)
        return advisory_response
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "AdvisoryWorkflowExecutionError",
                "message": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


# ==========================================
# Speech & VHF Audio Transmission Endpoints
# ==========================================

class SpeechTTSRequest(BaseModel):
    text: str
    language: Optional[str] = "en"


@app.post(
    f"{settings.API_V1_STR}/speech/tts",
    tags=["Advisory & Conversational AI"],
    summary="Synthesize Marine VHF Audio Broadcast (Neural Edge-TTS)",
    description="Generates native Indian marine broadcast speech audio (MP3 base64) using Edge-TTS with regional voices."
)
async def speech_text_to_speech(payload: SpeechTTSRequest):
    result = await synthesize_speech(text=payload.text, language=payload.language or "en")
    return JSONResponse(content=result)


@app.post(
    f"{settings.API_V1_STR}/speech/stt",
    tags=["Advisory & Conversational AI"],
    summary="Process Microphone Audio File (STT)",
    description="Accepts an audio file recorded by the client device microphone, transcribes it, and returns the query text."
)
async def speech_audio_to_text(file: UploadFile = File(...), language: Optional[str] = Query("auto")):
    contents = await file.read()
    result = await process_speech_audio(audio_bytes=contents, filename=file.filename or "speech.webm", language=language or "auto")
    return JSONResponse(content=result)


# ==========================================
# Direct Tool Diagnostic Endpoints
# ==========================================

@app.post(
    f"{settings.API_V1_STR}/route/plan",
    response_model=RouteOptimization,
    tags=["Route Optimization"],
    summary="Plan Safest Nautical Navigation Route",
    description="Calculates safe navigation tracks from start point to destination, avoiding MPAs and border buffer zones."
)
async def direct_route_plan(
    start_lat: float = Query(..., ge=-90.0, le=90.0, description="Start latitude", examples=[9.9312]),
    start_lon: float = Query(..., ge=-180.0, le=180.0, description="Start longitude", examples=[76.2673]),
    target_lat: Optional[float] = Query(None, description="Target hotspot latitude"),
    target_lon: Optional[float] = Query(None, description="Target hotspot longitude"),
    cruising_speed_knots: float = Query(8.5, description="Cruising speed in knots")
) -> RouteOptimization:
    res = route_engine.plan_safest_route(start_lat, start_lon, target_lat, target_lon, cruising_speed_knots)
    return RouteOptimization(
        total_distance_nm=res["total_distance_nm"],
        initial_bearing_deg=res["initial_bearing_deg"],
        recommended_cruising_speed_knots=res["recommended_cruising_speed_knots"],
        estimated_transit_time_hours=res["estimated_transit_time_hours"],
        waypoints=res["waypoints"],
        summary=res["summary"]
    )


@app.get(
    f"{settings.API_V1_STR}/tides/current",
    response_model=TidalCondition,
    tags=["Tides & Harbor Safety"],
    summary="Current Tidal State & High/Low Predictions",
    description="Computes astronomical tide heights and next high/low tide predictions for coastal coordinates."
)
async def get_current_tides(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees", examples=[9.9312]),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees", examples=[76.2673])
) -> TidalCondition:
    res = tide_engine.compute_tide_assessment(latitude, longitude)
    return TidalCondition(**res)


@app.get(
    f"{settings.API_V1_STR}/geocoding/resolve",
    response_model=GeocodingInfo,
    tags=["Geocoding"],
    summary="Resolve Coastal Location Name to Coordinates",
    description="Resolves 100+ Indian coastal ports, harbors, and maritime landing centers to precise coordinates."
)
async def resolve_coastal_location(
    location_name: str = Query(..., description="Port or coastal landmark name (e.g. Mangalore, Cochin, Veraval, Vizag, Rameswaram)", examples=["Mangalore"])
) -> GeocodingInfo:
    res = await geocoder.geocode_query(location_name)
    if not res:
        raise HTTPException(status_code=404, detail=f"Location '{location_name}' could not be resolved to an Indian coastal coordinate.")
    return GeocodingInfo(
        resolved_name=res["name"],
        latitude=res["latitude"],
        longitude=res["longitude"],
        state=res.get("state"),
        matched_by=res["matched_by"]
    )


@app.post(
    f"{settings.API_V1_STR}/geofence/check",
    response_model=GeofenceCondition,
    tags=["Geofence & Boundaries"],
    summary="Direct Maritime Boundary & Geofence Probe",
    description="Evaluates whether given coordinates fall inside the Indian EEZ, near neighboring maritime borders (IMBL), or inside a restricted Marine Protected Area (MPA)."
)
async def direct_geofence_check(payload: GeofenceCheckRequest) -> GeofenceCondition:
    try:
        res = await geofence_adapter.check_geofence(payload.latitude, payload.longitude)
        return GeofenceCondition(**res["condition"])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Geofence evaluation failed: {str(exc)}"
        )


@app.get(
    f"{settings.API_V1_STR}/geofence/status",
    response_model=GeofenceCondition,
    tags=["Geofence & Boundaries"],
    summary="Quick Geofence Status Lookup",
    description="Quick GET endpoint for checking coordinates geofence compliance via query parameters."
)
async def quick_geofence_status(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees", examples=[9.9312]),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees", examples=[76.2673])
) -> GeofenceCondition:
    res = await geofence_adapter.check_geofence(latitude, longitude)
    return GeofenceCondition(**res["condition"])


@app.post(
    f"{settings.API_V1_STR}/weather/check",
    response_model=WeatherCondition,
    tags=["Weather & Meteorology"],
    summary="Direct Marine Weather Assessment",
    description="Directly queries marine meteorological conditions (wind speed, wave height, swell period, visibility) and evaluates safety status."
)
async def direct_weather_check(payload: WeatherCheckRequest) -> WeatherCondition:
    try:
        res = await weather_adapter.get_weather_assessment(payload.latitude, payload.longitude)
        return WeatherCondition(**res["condition"])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Weather evaluation failed: {str(exc)}"
        )


@app.post(
    f"{settings.API_V1_STR}/ocean/pfz",
    response_model=OceanCondition,
    tags=["Oceanography & PFZ"],
    summary="Direct Oceanographic & PFZ Probe",
    description="Directly evaluates Sea Surface Temperature (SST), Chlorophyll-a concentration, surface current velocity, and Potential Fishing Zone (PFZ) suitability."
)
async def direct_ocean_pfz_check(payload: OceanCheckRequest) -> OceanCondition:
    try:
        res = await ocean_adapter.get_ocean_assessment(payload.latitude, payload.longitude, payload.target_species)
        return OceanCondition(**res["condition"])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Oceanographic evaluation failed: {str(exc)}"
        )


# ==========================================
# Cache Telemetry & Invalidation Endpoints
# ==========================================

@app.get(
    f"{settings.API_V1_STR}/cache/stats",
    response_model=CacheStatsResponse,
    tags=["Cache & Performance"],
    summary="Get Spatial Cache Telemetry",
    description="Returns cache hit/miss counts, hit ratio percentage, active in-memory entries, and Redis connection state."
)
async def get_cache_stats() -> CacheStatsResponse:
    stats = await cache.get_stats()
    return CacheStatsResponse(**stats)


@app.post(
    f"{settings.API_V1_STR}/cache/clear",
    tags=["Cache & Performance"],
    summary="Invalidate Spatial Cache",
    description="Flushes all cached spatial query records from Redis and in-memory storage."
)
async def clear_cache():
    cleared_count = await cache.clear()
    return {
        "status": "success",
        "message": f"Flushed {cleared_count} cached spatial entries.",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ==========================================
# Interactive Client Frontend Dashboard & Static Assets
# ==========================================

client_html_path = os.path.join(os.path.dirname(__file__), "client", "index.html")
assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

@app.get("/oceanova", response_class=HTMLResponse, tags=["System & Telemetry"], summary="Oceanova Marine Intelligence Platform")
@app.get("/marlin", response_class=HTMLResponse, tags=["System & Telemetry"], summary="Oceanova Marine Intelligence Platform (Alias)")
@app.get("/client", response_class=HTMLResponse, tags=["System & Telemetry"], summary="Interactive Frontend Client")
@app.get("/app", response_class=HTMLResponse, tags=["System & Telemetry"], summary="Interactive Frontend Client (Alias)")
async def serve_client_dashboard():
    """Serves the interactive Oceanova marine intelligence client platform."""
    if os.path.exists(client_html_path):
        with open(client_html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    return HTMLResponse(
        content="""
        <html>
            <head><title>Oceanova API</title></head>
            <body style="font-family: sans-serif; padding: 2rem; background: #05070a; color: white;">
                <h1>🌊 Project Oceanova</h1>
                <p>Interactive platform initializing. Visit <a href="/docs" style="color: #38bdf8;">/docs</a> for Swagger UI.</p>
            </body>
        </html>
        """,
        status_code=200
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)