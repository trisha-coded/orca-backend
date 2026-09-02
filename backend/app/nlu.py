import re
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple, List
import urllib.request
import urllib.parse
import json

# Pre-cached registry of major Indian coastal fishing ports, harbors, and maritime cities
COASTAL_PORTS_REGISTRY: Dict[str, Dict[str, Any]] = {
    # Karnataka
    "mangalore": {"lat": 12.9141, "lon": 74.8560, "name": "Mangalore Port", "state": "Karnataka"},
    "mangaluru": {"lat": 12.9141, "lon": 74.8560, "name": "Mangalore Port", "state": "Karnataka"},
    "malpe": {"lat": 13.3533, "lon": 74.7006, "name": "Malpe Fishing Harbor", "state": "Karnataka"},
    "udupi": {"lat": 13.3409, "lon": 74.7421, "name": "Udupi Coast", "state": "Karnataka"},
    "karwar": {"lat": 14.8136, "lon": 74.1298, "name": "Karwar Harbor", "state": "Karnataka"},
    "honnavar": {"lat": 14.2800, "lon": 74.4400, "name": "Honnavar Port", "state": "Karnataka"},
    "bhatkal": {"lat": 13.9856, "lon": 74.5511, "name": "Bhatkal Coast", "state": "Karnataka"},
    
    # Kerala
    "kochi": {"lat": 9.9312, "lon": 76.2673, "name": "Kochi Harbor", "state": "Kerala"},
    "cochin": {"lat": 9.9312, "lon": 76.2673, "name": "Kochi Harbor", "state": "Kerala"},
    "munambam": {"lat": 10.1822, "lon": 76.1625, "name": "Munambam Fishing Harbor", "state": "Kerala"},
    "beypore": {"lat": 11.1628, "lon": 75.8058, "name": "Beypore Port", "state": "Kerala"},
    "calicut": {"lat": 11.2588, "lon": 75.7804, "name": "Kozhikode/Calicut Coast", "state": "Kerala"},
    "kozhikode": {"lat": 11.2588, "lon": 75.7804, "name": "Kozhikode Coast", "state": "Kerala"},
    "kollam": {"lat": 8.8932, "lon": 76.6141, "name": "Needakara/Kollam Port", "state": "Kerala"},
    "vizhinjam": {"lat": 8.3792, "lon": 76.9936, "name": "Vizhinjam International Port", "state": "Kerala"},
    "trivandrum": {"lat": 8.5241, "lon": 76.9366, "name": "Thiruvananthapuram Coast", "state": "Kerala"},
    "kasaragod": {"lat": 12.5000, "lon": 74.9833, "name": "Kasaragod Port", "state": "Kerala"},
    "kannur": {"lat": 11.8745, "lon": 75.3704, "name": "Azheekal/Kannur Harbor", "state": "Kerala"},

    # Tamil Nadu & Puducherry
    "chennai": {"lat": 13.0827, "lon": 80.2707, "name": "Chennai Royapuram Harbor", "state": "Tamil Nadu"},
    "madras": {"lat": 13.0827, "lon": 80.2707, "name": "Chennai Harbor", "state": "Tamil Nadu"},
    "tuticorin": {"lat": 8.7642, "lon": 78.1348, "name": "Thoothukudi / Tuticorin Port", "state": "Tamil Nadu"},
    "thoothukudi": {"lat": 8.7642, "lon": 78.1348, "name": "Thoothukudi Port", "state": "Tamil Nadu"},
    "kanyakumari": {"lat": 8.0883, "lon": 77.5385, "name": "Kanyakumari Coast", "state": "Tamil Nadu"},
    "nagapattinam": {"lat": 10.7656, "lon": 79.8424, "name": "Nagapattinam Fishing Harbor", "state": "Tamil Nadu"},
    "cuddalore": {"lat": 11.7480, "lon": 79.7714, "name": "Cuddalore Port", "state": "Tamil Nadu"},
    "puducherry": {"lat": 11.9416, "lon": 79.8083, "name": "Puducherry Fishing Harbor", "state": "Puducherry"},
    "pondicherry": {"lat": 11.9416, "lon": 79.8083, "name": "Puducherry Fishing Harbor", "state": "Puducherry"},
    "pamban": {"lat": 9.2800, "lon": 79.2000, "name": "Pamban / Rameswaram Coast", "state": "Tamil Nadu"},
    "rameswaram": {"lat": 9.2876, "lon": 79.3129, "name": "Rameswaram Fishing Harbor", "state": "Tamil Nadu"},

    # Maharashtra & Goa
    "mumbai": {"lat": 18.9438, "lon": 72.8359, "name": "Sassoon Dock / Mumbai Harbor", "state": "Maharashtra"},
    "ratnagiri": {"lat": 16.9902, "lon": 73.3120, "name": "Ratnagiri Mirkarwada Port", "state": "Maharashtra"},
    "alibaug": {"lat": 18.6414, "lon": 72.8722, "name": "Alibaug Coast", "state": "Maharashtra"},
    "dahanu": {"lat": 19.9705, "lon": 72.7350, "name": "Dahanu Fishing Coast", "state": "Maharashtra"},
    "goa": {"lat": 15.4989, "lon": 73.8278, "name": "Panaji / Mormugao Port", "state": "Goa"},
    "panaji": {"lat": 15.4989, "lon": 73.8278, "name": "Panaji Coast", "state": "Goa"},
    "mormugao": {"lat": 15.4050, "lon": 73.7995, "name": "Mormugao Harbor", "state": "Goa"},

    # Gujarat, Daman & Diu
    "veraval": {"lat": 20.9000, "lon": 70.3667, "name": "Veraval Fishing Port", "state": "Gujarat"},
    "porbandar": {"lat": 21.6417, "lon": 69.6293, "name": "Porbandar Harbor", "state": "Gujarat"},
    "okha": {"lat": 22.4667, "lon": 69.0667, "name": "Okha Fishing Port", "state": "Gujarat"},
    "dwarka": {"lat": 22.2394, "lon": 68.9678, "name": "Dwarka Coast", "state": "Gujarat"},
    "jafrabad": {"lat": 20.8680, "lon": 71.3650, "name": "Jafrabad Fishing Harbor", "state": "Gujarat"},
    "diu": {"lat": 20.7144, "lon": 70.9874, "name": "Diu Harbor", "state": "Daman and Diu"},

    # Andhra Pradesh & Odisha & West Bengal
    "visakhapatnam": {"lat": 17.6868, "lon": 83.2185, "name": "Visakhapatnam Fishing Harbor", "state": "Andhra Pradesh"},
    "vizag": {"lat": 17.6868, "lon": 83.2185, "name": "Visakhapatnam Harbor", "state": "Andhra Pradesh"},
    "kakinada": {"lat": 16.9891, "lon": 82.2475, "name": "Kakinada Deepwater Port", "state": "Andhra Pradesh"},
    "machilipatnam": {"lat": 16.1824, "lon": 81.1362, "name": "Machilipatnam Port", "state": "Andhra Pradesh"},
    "puri": {"lat": 19.8135, "lon": 85.8312, "name": "Puri Fishing Coast", "state": "Odisha"},
    "paradip": {"lat": 20.3164, "lon": 86.6111, "name": "Paradip Fishing Harbor", "state": "Odisha"},
    "dhamra": {"lat": 20.8000, "lon": 86.9100, "name": "Dhamra Port", "state": "Odisha"},
    "digha": {"lat": 21.6266, "lon": 87.5074, "name": "Digha Shankarpur Fishing Harbor", "state": "West Bengal"},
    "kakdwip": {"lat": 21.8761, "lon": 88.1856, "name": "Kakdwip Sundarbans Port", "state": "West Bengal"},

    # Andaman & Lakshadweep
    "port blair": {"lat": 11.6234, "lon": 92.7265, "name": "Port Blair Harbor", "state": "Andaman & Nicobar"},
    "kavaratti": {"lat": 10.5667, "lon": 72.6417, "name": "Kavaratti Island", "state": "Lakshadweep"},
}


def geocode_location(query: str) -> Optional[Dict[str, Any]]:
    """
    Extracts coastal location name from natural language query and resolves to (lat, lon).
    Uses high-speed local registry first, followed by online OpenStreetMap Nominatim fallback.
    """
    clean_query = query.lower()

    # 1. Exact or Substring match against pre-cached coastal registry
    for key, data in COASTAL_PORTS_REGISTRY.items():
        # Match whole word or location phrase
        pattern = r'\b' + re.escape(key) + r'\b'
        if re.search(pattern, clean_query):
            return {
                "location_name": data["name"],
                "state": data["state"],
                "latitude": data["lat"],
                "longitude": data["lon"],
                "source": "coastal_registry_exact"
            }

    # 2. Online Geocoding Fallback via Nominatim OpenStreetMap API
    try:
        # Extract potential proper nouns or place names
        place_keywords = [
            w for w in re.findall(r'\b[A-Za-z]{3,}\b', query)
            if w.lower() not in {"safe", "near", "today", "tomorrow", "weather", "fish", "fishing", "zone", "sea", "ocean", "what", "where", "is", "it", "for", "the", "next", "hours", "morning", "evening"}
        ]

        if place_keywords:
            search_target = " ".join(place_keywords) + ", India"
            url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(search_target)}&format=json&limit=1"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "AgenticMarineIntelligence/1.0 (marine-agent-geocoder)"}
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data and len(data) > 0:
                        item = data[0]
                        return {
                            "location_name": item.get("display_name", search_target).split(",")[0],
                            "state": "India Coastal Region",
                            "latitude": float(item["lat"]),
                            "longitude": float(item["lon"]),
                            "source": "nominatim_osm"
                        }
    except Exception as e:
        # Gracefully handle network timeouts/failures
        pass

    # 3. Default Fallback (Central West Coast - Kochi)
    return {
        "location_name": "Kochi Offshore (Default Coastal Benchmark)",
        "state": "Kerala",
        "latitude": 9.9312,
        "longitude": 76.2673,
        "source": "fallback_default"
    }


def parse_temporal_expression(query: str) -> Dict[str, Any]:
    """
    Parses temporal terms ('tomorrow', 'tomorrow morning', 'today', 'tonight', 'next 24 hours')
    into target datetimes and forecast hour offsets.
    """
    clean_query = query.lower()
    now_utc = datetime.now(timezone.utc)
    
    hours_offset = 0
    time_description = "Current Prevailing Conditions"

    if "tomorrow morning" in clean_query:
        hours_offset = 18  # Typical next morning window
        time_description = "Tomorrow Morning (06:00 - 12:00 IST)"
    elif "tomorrow evening" in clean_query or "tomorrow night" in clean_query:
        hours_offset = 30
        time_description = "Tomorrow Evening / Night"
    elif "tomorrow" in clean_query:
        hours_offset = 24
        time_description = "Tomorrow (+24 Hours Forecast)"
    elif "tonight" in clean_query or "this evening" in clean_query:
        hours_offset = 6
        time_description = "Tonight / This Evening"
    elif "next 24 hours" in clean_query or "next 24h" in clean_query:
        hours_offset = 12
        time_description = "Next 24 Hours Horizon"
    elif "today" in clean_query:
        hours_offset = 0
        time_description = "Today (Real-time)"

    target_dt = now_utc + timedelta(hours=hours_offset)

    return {
        "target_timestamp": target_dt.isoformat(),
        "hours_offset": hours_offset,
        "time_description": time_description,
    }


def classify_intent(query: str) -> str:
    """
    Identifies primary intent: SAFETY_CHECK, PFZ_LOCATION, WEATHER_FORECAST, BOUNDARY_ALERT.
    """
    clean_query = query.lower()

    if any(w in clean_query for w in ["safe", "safety", "hazard", "risk", "venture"]):
        return "SAFETY_CHECK"
    elif any(w in clean_query for w in ["pfz", "fish", "fishing", "catch", "chlorophyll", "tuna", "sardine", "mackerel"]):
        return "PFZ_LOCATION"
    elif any(w in clean_query for w in ["border", "imbl", "sri lanka", "pakistan", "restricted", "navy", "protected"]):
        return "BOUNDARY_ALERT"
    elif any(w in clean_query for w in ["wind", "wave", "cyclone", "storm", "lightning", "rain"]):
        return "WEATHER_FORECAST"
    else:
        return "SAFETY_CHECK"


def parse_natural_query(query: str, user_coords: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    Main Natural Language Understanding pipeline:
    - Resolves coordinates (User explicit > Geocoded entity > Coastal Default)
    - Resolves temporal window
    - Classifies intent
    """
    temporal_info = parse_temporal_expression(query)
    intent = classify_intent(query)

    if user_coords and "latitude" in user_coords and "longitude" in user_coords:
        location_info = {
            "location_name": f"Coordinates ({user_coords['latitude']:.4f}, {user_coords['longitude']:.4f})",
            "state": "Explicit Coordinates",
            "latitude": user_coords["latitude"],
            "longitude": user_coords["longitude"],
            "source": "explicit_user_input"
        }
    else:
        location_info = geocode_location(query)

    return {
        "raw_query": query,
        "intent": intent,
        "location": location_info,
        "temporal": temporal_info,
    }
