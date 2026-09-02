"""
Integration test suite for ORCA FastAPI server, Swagger UI OpenAPI schema, and endpoint routing.
Tests all client/frontend entrypoints, direct tools, cache telemetry, and safety gates.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_openapi_schema_generation():
    """Verify that OpenAPI schema generates correctly for Swagger UI."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert schema["info"]["title"] == "🌊 ORCA Marine Intelligence Platform - API"
    assert "/api/v1/advisory" in schema["paths"]
    assert "/api/v1/geofence/check" in schema["paths"]
    assert "/api/v1/weather/check" in schema["paths"]
    assert "/api/v1/ocean/pfz" in schema["paths"]
    assert "/api/v1/health" in schema["paths"]


def test_swagger_ui_docs():
    """Verify that Swagger UI (/docs) and ReDoc (/redoc) are accessible."""
    docs_res = client.get("/docs")
    assert docs_res.status_code == 200
    assert "swagger-ui" in docs_res.text.lower() or "html" in docs_res.text.lower()

    redoc_res = client.get("/redoc")
    assert redoc_res.status_code == 200


def test_root_service_discovery():
    """Verify root / discovery endpoint returns service metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPERATIONAL"
    assert data["docs_url"] == "/docs"
    assert data["client_app_url"] == "/client"
    assert data["advisory_endpoint"] == "/api/v1/advisory"


def test_health_check_endpoints():
    """Verify liveness and readiness health check endpoints."""
    # Root /health
    res1 = client.get("/health")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "healthy"
    assert "uptime_seconds" in data1
    assert data1["modules"]["supervisor_agent"] == "active"

    # API v1 /api/v1/health
    res2 = client.get("/api/v1/health")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "healthy"


def test_full_advisory_pipeline_cochin():
    """Verify end-to-end multi-agent advisory generation for Cochin waters."""
    payload = {
        "latitude": 9.9312,
        "longitude": 76.2673,
        "query": "Is it safe to sail for Yellowfin Tuna today?",
        "target_species": "Yellowfin Tuna",
        "vessel_type": "Motorized Boat",
        "language": "en",
        "session_id": "test_sess_01"
    }

    response = client.post("/api/v1/advisory", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "request_id" in data
    assert data["session_id"] == "test_sess_01"
    assert data["target_species"] == "Yellowfin Tuna"
    assert data["vessel_type"] == "Motorized Boat"
    assert data["safety_assessment"]["go_no_go_decision"] in ["GO", "GO_WITH_CAUTION", "NO_GO"]
    assert "ORCA MARINE ADVISORY" in data["advisory_text"]
    assert len(data["geojson"]["features"]) >= 1
    assert len(data["reasoning_logs"]) >= 3
    assert "X-Process-Time-Ms" in response.headers


def test_multilingual_advisory_tamil():
    """Verify Tamil synthesized advisory output."""
    payload = {
        "latitude": 13.0827,
        "longitude": 80.2707,
        "query": "மீன்பிடிக்க செல்வது பாதுகாப்பானதா?",
        "target_species": "Sardine",
        "vessel_type": "Motorized Boat",
        "language": "ta"
    }

    response = client.post("/api/v1/advisory", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "ta"
    assert "ஆர்கா" in data["advisory_text"]


def test_spatial_query_cache_hit():
    """Verify that repeating the same coordinates triggers a cache hit."""
    payload = {
        "latitude": 15.2993,
        "longitude": 74.1240,
        "query": "Goa coast tuna fishing safety",
        "target_species": "Tuna",
        "vessel_type": "Motorized Boat",
        "language": "en"
    }

    # First request -> cache miss
    res1 = client.post("/api/v1/advisory", json=payload)
    assert res1.status_code == 200

    # Second request -> cache hit
    res2 = client.post("/api/v1/advisory", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["cached"] is True


def test_direct_geofence_check_endpoint():
    """Verify direct POST /api/v1/geofence/check."""
    payload = {
        "latitude": 9.9312,
        "longitude": 76.2673,
        "vessel_type": "Motorized Boat"
    }
    response = client.post("/api/v1/geofence/check", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["within_indian_eez"] is True
    assert data["border_alert_level"] == "CLEAR"


def test_quick_geofence_status_get():
    """Verify quick GET /api/v1/geofence/status."""
    response = client.get("/api/v1/geofence/status?latitude=9.9312&longitude=76.2673")
    assert response.status_code == 200
    data = response.json()
    assert data["within_indian_eez"] is True


def test_direct_weather_check_endpoint():
    """Verify direct POST /api/v1/weather/check."""
    payload = {
        "latitude": 13.0827,
        "longitude": 80.2707
    }
    response = client.post("/api/v1/weather/check", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "wind_speed_knots" in data
    assert "wave_height_m" in data
    assert data["status"] in ["SAFE", "CAUTION", "DANGEROUS"]


def test_direct_ocean_pfz_endpoint():
    """Verify direct POST /api/v1/ocean/pfz."""
    payload = {
        "latitude": 17.6868,
        "longitude": 83.2185,
        "target_species": "Yellowfin Tuna"
    }
    response = client.post("/api/v1/ocean/pfz", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "sea_surface_temperature_c" in data
    assert "chlorophyll_a_mg_m3" in data
    assert "pfz_potential_score" in data
    assert data["pfz_rating"] in ["HIGH", "MODERATE", "LOW"]


def test_cache_telemetry_and_clear():
    """Verify GET /api/v1/cache/stats and POST /api/v1/cache/clear."""
    stats_res = client.get("/api/v1/cache/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert "hits" in stats
    assert "misses" in stats
    assert "hit_ratio_percent" in stats

    clear_res = client.post("/api/v1/cache/clear")
    assert clear_res.status_code == 200
    assert clear_res.json()["status"] == "success"


def test_client_dashboard_serving():
    """Verify GET /client serves HTML dashboard."""
    response = client.get("/client")
    assert response.status_code == 200
    assert "ORCA Marine Intelligence" in response.text
    assert "leaflet" in response.text.lower()
