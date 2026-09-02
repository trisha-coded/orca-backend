import pytest
from app.tools.geofence_tools import check_geofence_and_imbl
from app.tools.weather_tools import fetch_marine_weather, simulate_indian_waters_weather
from app.tools.ocean_tools import fetch_oceanographic_data
from app.agents.supervisor import supervisor_intent_parser
from app.agents.synthesizer import safety_evaluator_node, synthesizer_node
from app.graph import run_marine_decision_pipeline
from app.state import MarineAgentState


@pytest.mark.asyncio
async def test_geofence_imbl_proximity_detection():
    # Coordinates in Palk Strait near IMBL (Rameswaram / Palk Bay)
    lat, lon = 9.35, 79.40
    res = check_geofence_and_imbl(lat, lon)
    
    assert "India" in res["nearest_imbl_name"] or "Sri Lanka" in res["nearest_imbl_name"]
    assert res["distance_to_imbl_nm"] < 10.0
    assert res["buffer_alert_level"] in ["CRITICAL_PROXIMITY", "WARNING", "BREACH", "SAFE"]
    assert len(res["geojson_features"]) >= 3


@pytest.mark.asyncio
async def test_weather_and_ocean_tools():
    # Test coastal Tamil Nadu
    lat, lon = 9.28, 79.31
    weather = await fetch_marine_weather(lat, lon)
    assert weather["wind_speed_knots"] > 0
    assert weather["wave_height_m"] > 0
    assert 0 <= weather["cyclonic_risk_score"] <= 1.0

    ocean = await fetch_oceanographic_data(lat, lon, target_species="tuna")
    assert 20.0 <= (ocean.get("sst_celsius") or 28.0) <= 35.0
    assert (ocean.get("chlorophyll_mg_m3") or 0.5) > 0
    assert len(ocean.get("target_species_recommendations", [])) > 0


@pytest.mark.asyncio
async def test_supervisor_intent_parser():
    state: MarineAgentState = {
        "query": "Is it safe to sail for Tuna catch near Sri Lanka border tonight?",
        "coordinates": {"latitude": 9.35, "longitude": 79.40},
        "vessel_context": {"vessel_type": "mechanized_trawler", "max_safe_wave_m": 2.5},
        "language": "ta",
        "audit_trail": [],
    }
    parsed = supervisor_intent_parser(state)
    assert parsed["parsed_intent"]["intent_type"] in [
        "FISHING_ZONE_OPTIMIZATION",
        "BORDER_SECURITY_AND_GEOFENCE",
    ]
    assert parsed["target_species"] == "Yellowfin Tuna"
    assert parsed["requires_geofence"] is True


@pytest.mark.asyncio
async def test_deterministic_safety_override_high_wave():
    # Simulate high wave state
    mock_state: MarineAgentState = {
        "query": "Can I go fishing?",
        "coordinates": {"latitude": 15.0, "longitude": 73.0},
        "vessel_context": {"max_safe_wave_m": 2.0, "max_safe_wind_knots": 20.0},
        "weather_data": {
            "wave_height_m": 3.8,  # > 2.0 and > 3.5
            "wind_speed_knots": 32.0,
            "cyclonic_risk_score": 0.2,
            "sea_state_description": "Rough",
        },
        "geofence_data": {
            "nearest_imbl_name": "Arabian Sea",
            "distance_to_imbl_nm": 50.0,
            "is_boundary_breach": False,
            "inside_mpa": False,
        },
        "language": "en",
        "audit_trail": [],
    }
    eval_state = safety_evaluator_node(mock_state)
    assert eval_state["safety_eval"]["override_triggered"] is True
    assert eval_state["safety_eval"]["alert_level"] == "RED"
    assert eval_state["safety_eval"]["is_safe_to_sail"] is False

    # Synthesizer must issue mandatory safety override in text
    synth_state = synthesizer_node(eval_state)
    assert "CRITICAL MARITIME SAFETY OVERRIDE" in synth_state["advisory_title"]
    assert "SUSPENDED" in synth_state["advisory_body"]


@pytest.mark.asyncio
async def test_end_to_end_decision_pipeline_multilingual_tamil():
    # End-to-end test with Tamil language request
    initial_state: MarineAgentState = {
        "query": "இன்று மீன்பிடிக்க செல்லலாமா? (Can we go fishing today?)",
        "coordinates": {"latitude": 9.28, "longitude": 79.31},
        "vessel_context": {
            "vessel_type": "mechanized_trawler",
            "length_m": 14.0,
            "max_safe_wave_m": 3.0,
            "max_safe_wind_knots": 25.0,
        },
        "language": "ta",
        "audit_trail": [],
    }
    final_state = await run_marine_decision_pipeline(initial_state)

    assert "advisory_title" in final_state
    assert len(final_state["advisory_title"]) > 0
    assert "spatial_features" in final_state
    assert final_state["spatial_features"]["type"] == "FeatureCollection"
    assert len(final_state["spatial_features"]["features"]) > 0
    assert len(final_state["audit_trail"]) >= 4
