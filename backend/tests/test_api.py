import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "supervisor" in data["modules"]
    assert "deterministic_safety_gate" in data["modules"]


def test_direct_geofence_check_endpoint():
    # Palk Strait location near Sri Lanka border
    response = client.post("/api/v1/geofence/check?lat=9.35&lon=79.40")
    assert response.status_code == 200
    data = response.json()
    assert "India" in data["nearest_imbl_name"] or "Sri Lanka" in data["nearest_imbl_name"]
    assert data["distance_to_imbl_nm"] > 0
    assert "geojson_features" in data


def test_direct_weather_check_endpoint():
    response = client.post("/api/v1/weather/check?lat=9.28&lon=79.31")
    assert response.status_code == 200
    data = response.json()
    assert "wind_speed_knots" in data
    assert "wave_height_m" in data
    assert "sea_state_description" in data


def test_direct_pfz_check_endpoint():
    response = client.post("/api/v1/ocean/pfz?lat=9.28&lon=79.31&target_species=tuna")
    assert response.status_code == 200
    data = response.json()
    assert "sst_celsius" in data
    assert "chlorophyll_mg_m3" in data
    assert "target_species_recommendations" in data


def test_full_advisory_pipeline_endpoint():
    payload = {
        "query": "Is it safe to fish for tuna near Rameswaram and Kachchatheevu?",
        "coordinates": {
            "latitude": 9.35,
            "longitude": 79.40,
        },
        "vessel_context": {
            "vessel_type": "mechanized_trawler",
            "vessel_id": "IND-TN-08-MM-552",
            "max_safe_wave_m": 2.5,
            "max_safe_wind_knots": 22.0,
        },
        "language": "en",
        "target_species": "tuna",
    }

    response = client.post("/api/v1/advisory", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "request_id" in data
    assert "safety_status" in data
    assert "advisory_title" in data
    assert "advisory_body" in data
    assert "audio_broadcast_script" in data
    assert "spatial_features" in data
    assert data["spatial_features"]["type"] == "FeatureCollection"
    assert len(data["audit_trail"]) >= 4
