import time
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.schemas import (
    MarineQueryRequest,
    MarineAdvisoryResponse,
    GeofenceAssessment,
    WeatherAssessment,
    OceanAssessment,
    SafetyStatus,
    GeoJSONFeatureCollection,
    AuditLogEntry,
)
from app.state import MarineAgentState
from app.graph import run_marine_decision_pipeline
from app.tools.geofence_tools import check_geofence_and_imbl
from app.tools.weather_tools import fetch_marine_weather
from app.tools.ocean_tools import fetch_oceanographic_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Initialization
    print(f"🚀 Initializing {settings.PROJECT_NAME} v{settings.PROJECT_VERSION}...")
    yield
    # Shutdown Cleanup
    print("🛑 Shutting down Decision-Support Engine.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="Agentic Marine Intelligence Platform - Multi-Agent Decision-Support Engine",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from pathlib import Path
from fastapi.staticfiles import StaticFiles

# Mount Frontend App if available
frontend_path = Path(__file__).resolve().parent.parent.parent / "FRONTEND" / "SIH"
if frontend_path.exists():
    app.mount("/app", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


@app.get("/", tags=["General"])
async def root_info():
    """Root metadata & service discovery."""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "environment": settings.ENVIRONMENT,
        "status": "OPERATIONAL",
        "docs_url": "/docs",
        "frontend_app_url": "/app/index.html",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health", tags=["Health"])
@app.get(f"{settings.API_V1_PREFIX}/health", tags=["Health"])
async def health_check():
    """Liveness & readiness health probe."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "modules": {
            "supervisor": "active",
            "weather_tools": "active",
            "ocean_tools": "active",
            "geofence_tools": "active",
            "deterministic_safety_gate": "active",
            "multilingual_synthesizer": "active",
        },
    }


@app.post(
    f"{settings.API_V1_PREFIX}/advisory",
    response_model=MarineAdvisoryResponse,
    tags=["Decision Support"],
    summary="Process natural language marine query through multi-agent decision engine",
)
async def generate_marine_advisory(payload: MarineQueryRequest):
    """
    Main Decision-Support Pipeline:
    - Parses natural language intent & vessel constraints
    - Queries real-time / calibrated weather, oceanographic, and boundary geofences
    - Applies deterministic safety overrides (wave, wind, IMBL, MPA)
    - Synthesizes multilingual advice and GeoJSON mapping features
    """
    req_id = f"req-{uuid.uuid4().hex[:8]}"

    initial_state: MarineAgentState = {
        "request_id": req_id,
        "query": payload.query,
        "coordinates": payload.coordinates.model_dump(),
        "vessel_context": payload.vessel_context.model_dump() if payload.vessel_context else {},
        "language": payload.language.value,
        "target_species": payload.target_species,
        "audit_trail": [],
        "errors": [],
    }

    try:
        final_state = await run_marine_decision_pipeline(initial_state)

        # Assemble Schema Response
        weather_dict = final_state.get("weather_data", {})
        ocean_dict = final_state.get("ocean_data", {})
        geofence_dict = final_state.get("geofence_data", {})
        safety_dict = final_state.get("safety_eval", {})
        spatial_dict = final_state.get("spatial_features", {})

        return MarineAdvisoryResponse(
            request_id=req_id,
            timestamp=datetime.now(timezone.utc),
            language=payload.language,
            query=payload.query,
            safety_status=SafetyStatus(**safety_dict),
            advisory_title=final_state.get("advisory_title", "Marine Advisory"),
            advisory_body=final_state.get("advisory_body", ""),
            audio_broadcast_script=final_state.get("audio_broadcast_script", ""),
            recommended_heading_deg=final_state.get("recommended_heading_deg"),
            recommended_speed_knots=final_state.get("recommended_speed_knots"),
            weather=WeatherAssessment(**weather_dict),
            ocean=OceanAssessment(**ocean_dict),
            geofence=GeofenceAssessment(**geofence_dict),
            spatial_features=GeoJSONFeatureCollection(**spatial_dict),
            audit_trail=[AuditLogEntry(**entry) for entry in final_state.get("audit_trail", [])],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline processing failed: {str(e)}",
        )


@app.post(
    f"{settings.API_V1_PREFIX}/geofence/check",
    response_model=GeofenceAssessment,
    tags=["Tools"],
    summary="Direct spatial geofence & IMBL distance check",
)
async def check_geofence(lat: float, lon: float, vessel_type: str = "mechanized_trawler"):
    """Validates distance to nearest IMBL, Indian EEZ, and MPAs."""
    try:
        res = check_geofence_and_imbl(lat, lon, vessel_type=vessel_type)
        return GeofenceAssessment(**res)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Geofence evaluation failed: {str(e)}",
        )


@app.post(
    f"{settings.API_V1_PREFIX}/weather/check",
    response_model=WeatherAssessment,
    tags=["Tools"],
    summary="Direct marine weather evaluation",
)
async def check_weather(lat: float, lon: float):
    """Fetches wind, waves, sea state, and cyclonic risk."""
    try:
        res = await fetch_marine_weather(lat, lon)
        res["is_safe"] = res["wave_height_m"] <= settings.MAX_SAFE_WAVE_HEIGHT_M
        res["advisory_notes"] = []
        return WeatherAssessment(**res)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Weather query failed: {str(e)}",
        )


@app.post(
    f"{settings.API_V1_PREFIX}/ocean/pfz",
    response_model=OceanAssessment,
    tags=["Tools"],
    summary="Direct PFZ & oceanographic suitability check",
)
async def check_pfz(lat: float, lon: float, target_species: str = None):
    """Analyzes SST, chlorophyll-a, upwelling, and PFZ probability."""
    try:
        res = await fetch_oceanographic_data(lat, lon, target_species=target_species)
        return OceanAssessment(**res)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Oceanographic query failed: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
