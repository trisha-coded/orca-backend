import pytest
from app.nlu import parse_natural_query, geocode_location, parse_temporal_expression, classify_intent


def test_coastal_geocoding_exact():
    res = geocode_location("Is it safe near Mangalore tomorrow morning?")
    assert res is not None
    assert "Mangalore" in res["location_name"]
    assert res["state"] == "Karnataka"
    assert round(res["latitude"], 2) == 12.91
    assert round(res["longitude"], 2) == 74.86


def test_coastal_geocoding_kochi():
    res = geocode_location("Where is the nearest PFZ near Kochi today?")
    assert res is not None
    assert "Kochi" in res["location_name"]
    assert res["state"] == "Kerala"
    assert round(res["latitude"], 2) == 9.93
    assert round(res["longitude"], 2) == 76.27


def test_coastal_geocoding_veraval():
    res = geocode_location("Check weather near Veraval coast")
    assert res is not None
    assert "Veraval" in res["location_name"]
    assert res["state"] == "Gujarat"


def test_temporal_parsing_tomorrow():
    temp = parse_temporal_expression("Is it safe near Mangalore tomorrow?")
    assert temp["hours_offset"] == 24
    assert "Tomorrow" in temp["time_description"]


def test_temporal_parsing_tomorrow_morning():
    temp = parse_temporal_expression("Is it safe near Chennai tomorrow morning?")
    assert temp["hours_offset"] == 18
    assert "Tomorrow Morning" in temp["time_description"]


def test_intent_classification():
    assert classify_intent("Is it safe near Mangalore tomorrow?") == "SAFETY_CHECK"
    assert classify_intent("Where is the nearest PFZ for tuna?") == "PFZ_LOCATION"
    assert classify_intent("Are there storm or cyclone alerts near Kochi?") == "WEATHER_FORECAST"
    assert classify_intent("Am I close to Sri Lanka border?") == "BOUNDARY_ALERT"


def test_full_nlu_pipeline():
    parsed = parse_natural_query("Is it safe to fish near Mangalore tomorrow morning?")
    assert parsed["intent"] == "SAFETY_CHECK"
    assert parsed["location"]["latitude"] == 12.9141
    assert parsed["temporal"]["hours_offset"] == 18
