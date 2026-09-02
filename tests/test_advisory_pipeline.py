"""
Comprehensive unit and integration test suite for the ORCA backend.
"""

import unittest
import asyncio
from app.schemas import MarineAdvisoryRequest, MarineAdvisoryResponse
from app.agents.supervisor import supervisor_agent
from app.agents.domain_agents import domain_agents
from app.agents.synthesizer import synthesizer_agent
from app.tools.geofence_tools import geofence_adapter
from app.tools.weather_tools import weather_adapter
from app.tools.ocean_tools import ocean_adapter
from app.cache import cache
from app.graph import orchestrator


class TestSupervisorAgent(unittest.TestCase):
    def test_intent_and_species_extraction(self):
        intent, entities = supervisor_agent.extract_intent_and_entities(
            "Can I go fishing for yellowfin tuna near Cochin?", None
        )
        self.assertEqual(intent, "FISHING_ADVISORY")
        self.assertEqual(entities.get("target_species"), "Yellowfin Tuna")

    def test_geofence_intent_extraction(self):
        intent, entities = supervisor_agent.extract_intent_and_entities(
            "Am I too close to the Sri Lanka maritime border?", None
        )
        self.assertEqual(intent, "NAVIGATION_AND_GEOFENCE")


class TestGeofenceAdapter(unittest.IsolatedAsyncioTestCase):
    async def test_indian_eez_point(self):
        # Cochin coastal waters (9.93° N, 76.26° E)
        res = await geofence_adapter.check_geofence(9.93, 76.26)
        cond = res["condition"]
        self.assertTrue(cond["within_indian_eez"])
        self.assertFalse(cond["in_mpa_zone"])
        self.assertEqual(cond["border_alert_level"], "CLEAR")

    async def test_gulf_of_mannar_mpa(self):
        # Inside Gulf of Mannar Marine National Park (9.0° N, 79.0° E)
        res = await geofence_adapter.check_geofence(9.0, 79.0)
        cond = res["condition"]
        self.assertTrue(cond["in_mpa_zone"])
        self.assertEqual(cond["border_alert_level"], "MPA_RESTRICTION")
        self.assertIn("Gulf of Mannar", cond["mpa_name"])


class TestSafetyGateAndSynthesizer(unittest.IsolatedAsyncioTestCase):
    async def test_safety_gate_dangerous_weather(self):
        weather_dangerous = {
            "status": "DANGEROUS",
            "warnings": ["High wave hazard: 3.5m exceeds safe limit"],
            "condition": {
                "wind_speed_knots": 28.0,
                "wave_height_m": 3.5,
                "wave_period_s": 7.0
            }
        }
        ocean_dummy = {
            "condition": {
                "sea_surface_temperature_c": 28.5,
                "chlorophyll_a_mg_m3": 0.6,
                "pfz_rating": "HIGH",
                "pfz_potential_score": 85.0
            }
        }
        geofence_dummy = {
            "condition": {
                "border_alert_level": "CLEAR",
                "within_indian_eez": True,
                "summary": "Inside Indian EEZ"
            }
        }

        safety = synthesizer_agent.evaluate_safety_gate(weather_dangerous, ocean_dummy, geofence_dummy)
        self.assertEqual(safety.go_no_go_decision, "NO_GO")
        self.assertEqual(safety.overall_safety_status, "DANGEROUS")
        self.assertLess(safety.safety_score, 60)

    async def test_multilingual_advisory_generation(self):
        state = {
            "latitude": 9.93,
            "longitude": 76.26,
            "language": "ta",
            "target_species": "Tuna",
            "vessel_type": "Motorized Boat",
            "weather_data": {
                "status": "SAFE",
                "condition": {"wind_speed_knots": 12.0, "wave_height_m": 1.1, "wave_period_s": 6.0}
            },
            "ocean_data": {
                "condition": {
                    "sea_surface_temperature_c": 28.5,
                    "chlorophyll_a_mg_m3": 0.7,
                    "pfz_rating": "HIGH",
                    "pfz_potential_score": 82.0
                },
                "hotspots": []
            },
            "geofence_data": {
                "condition": {
                    "within_indian_eez": True,
                    "border_alert_level": "CLEAR",
                    "nearest_country": "Sri Lanka",
                    "nearest_boundary_distance_nm": 45.0,
                    "summary": "Clear in EEZ"
                }
            }
        }

        out = await synthesizer_agent.execute(state)
        self.assertIn("ஆர்கா", out["advisory_text"])
        self.assertIsNotNone(out["geojson"])


class TestEndToEndWorkflow(unittest.IsolatedAsyncioTestCase):
    async def test_full_orchestrator_pipeline(self):
        req = MarineAdvisoryRequest(
            latitude=13.0827,
            longitude=80.2707,
            query="Is it safe for a small motorized boat to fish for Sardines today off Chennai?",
            target_species="Sardine",
            vessel_type="Motorized Boat",
            language="en"
        )

        response: MarineAdvisoryResponse = await orchestrator.run(req)

        self.assertIsNotNone(response.request_id)
        self.assertIsNotNone(response.advisory_text)
        self.assertIn(response.safety_assessment.go_no_go_decision, ["GO", "GO_WITH_CAUTION", "NO_GO"])
        self.assertGreaterEqual(len(response.geojson.features), 1)
        self.assertGreaterEqual(len(response.reasoning_logs), 3)

        # Test caching on repeated query
        cached_response: MarineAdvisoryResponse = await orchestrator.run(req)
        self.assertTrue(cached_response.cached)


if __name__ == "__main__":
    unittest.main()
