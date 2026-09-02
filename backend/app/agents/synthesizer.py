from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.config import settings
from app.state import MarineAgentState


def safety_evaluator_node(state: MarineAgentState) -> MarineAgentState:
    """
    Deterministic Safety Gate: Enforces hard safety overrides that supersede
    economic or fishing zone recommendations.
    """
    weather = state.get("weather_data", {})
    geofence = state.get("geofence_data", {})
    vessel = state.get("vessel_context", {})

    override_reasons = []
    override_triggered = False
    alert_level = "GREEN"
    enforcement_action = "PROCEED_WITH_NORMAL_NAVIGATION"

    # 1. Critical Boundary & Geofence Overrides
    imbl_dist = geofence.get("distance_to_imbl_nm", 100.0)
    is_breach = geofence.get("is_boundary_breach", False)
    inside_mpa = geofence.get("inside_mpa", False)

    if is_breach:
        override_triggered = True
        alert_level = "RED"
        override_reasons.append("CRITICAL: International Maritime Boundary Line breach detected.")
        enforcement_action = "EMERGENCY_REVERSE_COURSE_TO_INDIAN_WATERS"
    elif imbl_dist <= settings.IMBL_CRITICAL_BUFFER_NM:
        override_triggered = True
        alert_level = "RED"
        override_reasons.append(
            f"Vessel within critical buffer ({imbl_dist} NM) of {geofence.get('nearest_imbl_name')}."
        )
        enforcement_action = "ALTER_COURSE_INSHORE_IMMEDIATELY"
    elif inside_mpa:
        override_triggered = True
        alert_level = "ORANGE"
        override_reasons.append(f"Vessel inside restricted {geofence.get('mpa_name')}.")
        enforcement_action = "HAUL_NETS_AND_EXIT_PROTECTED_ZONE"
    elif imbl_dist <= settings.IMBL_WARNING_BUFFER_NM:
        alert_level = "YELLOW"
        override_reasons.append(f"Caution: Approaching maritime boundary ({imbl_dist} NM).")

    # 2. Weather & Sea State Overrides
    wave_h = weather.get("wave_height_m", 1.0)
    wind_spd = weather.get("wind_speed_knots", 10.0)
    cyclone_risk = weather.get("cyclonic_risk_score", 0.0)
    max_safe_wave = float(vessel.get("max_safe_wave_m", settings.MAX_SAFE_WAVE_HEIGHT_M))

    if wave_h > max_safe_wave or wave_h >= 3.5:
        override_triggered = True
        alert_level = "RED"
        override_reasons.append(
            f"Hazardous sea state: wave height {wave_h}m exceeds maximum safety tolerance ({max_safe_wave}m)."
        )
        enforcement_action = "RETURN_TO_PORT_OR_SEEK_SHELTER"

    if wind_spd >= settings.MAX_SAFE_WIND_SPEED_KNOTS:
        override_triggered = True
        alert_level = "RED"
        override_reasons.append(f"Gale force winds detected: {wind_spd} knots (threshold: {settings.MAX_SAFE_WIND_SPEED_KNOTS} knots).")
        enforcement_action = "RETURN_TO_PORT_OR_SEEK_SHELTER"

    if cyclone_risk >= settings.MAX_CYCLONIC_RISK_INDEX:
        override_triggered = True
        alert_level = "RED"
        override_reasons.append("Severe cyclonic depression risk detected.")
        enforcement_action = "CEASE_FISHING_AND_RETURN_TO_HARBOR"
    elif cyclone_risk >= 0.35 and alert_level == "GREEN":
        alert_level = "YELLOW"
        override_reasons.append("Moderate atmospheric depression alert.")

    is_safe_to_sail = not override_triggered

    safety_eval = {
        "is_safe_to_sail": is_safe_to_sail,
        "override_triggered": override_triggered,
        "override_reasons": override_reasons,
        "alert_level": alert_level,
        "enforcement_action": enforcement_action,
    }

    audit_trail = list(state.get("audit_trail", []))
    audit_trail.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "DeterministicSafetyEvaluator",
        "stage": "safety_gate",
        "action": "ENFORCE_SAFETY_GATE",
        "details": {
            "override_triggered": override_triggered,
            "alert_level": alert_level,
            "reasons": override_reasons,
        },
    })

    return {
        **state,
        "safety_eval": safety_eval,
        "override_triggered": override_triggered,
        "alert_level": alert_level,
        "audit_trail": audit_trail,
    }


def synthesizer_node(state: MarineAgentState) -> MarineAgentState:
    """
    Synthesizer Agent: Generates multilingual actionable marine advisory,
    VHF radio audio script, and GeoJSON spatial feature collection.
    """
    safety = state.get("safety_eval", {})
    weather = state.get("weather_data", {})
    ocean = state.get("ocean_data", {})
    geofence = state.get("geofence_data", {})
    lang = state.get("language", "en").lower()
    coords = state.get("coordinates", {})
    lat = float(coords.get("latitude", 9.28))
    lon = float(coords.get("longitude", 79.31))

    alert_level = safety.get("alert_level", "GREEN")
    is_safe = safety.get("is_safe_to_sail", True)
    reasons = safety.get("override_reasons", [])

    # Assemble Multilingual Content
    advisory_title, advisory_body, audio_script = _generate_multilingual_advisory(
        lang=lang,
        alert_level=alert_level,
        is_safe=is_safe,
        weather=weather,
        ocean=ocean,
        geofence=geofence,
        reasons=reasons,
        lat=lat,
        lon=lon,
    )

    # Calculate optimal heading recommendation (e.g., away from IMBL or towards port if unsafe)
    recommended_heading = None
    recommended_speed = None
    if not is_safe:
        recommended_heading = 270.0  # Steer Westward back towards Indian Coast
        recommended_speed = 8.0
    elif ocean.get("pfz_detected"):
        recommended_heading = round((ocean.get("current_direction_deg", 180.0) + 180.0) % 360.0, 1)
        recommended_speed = 6.5

    # Assemble Unified GeoJSON Feature Collection
    spatial_features = _assemble_geojson(lat, lon, weather, ocean, geofence, alert_level)

    audit_trail = list(state.get("audit_trail", []))
    audit_trail.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "SynthesizerAgent",
        "stage": "synthesis",
        "action": "GENERATE_MULTILINGUAL_ADVISORY_AND_GEOJSON",
        "details": {
            "language": lang,
            "alert_level": alert_level,
            "title": advisory_title,
        },
    })

    return {
        **state,
        "advisory_title": advisory_title,
        "advisory_body": advisory_body,
        "audio_broadcast_script": audio_script,
        "recommended_heading_deg": recommended_heading,
        "recommended_speed_knots": recommended_speed,
        "spatial_features": spatial_features,
        "audit_trail": audit_trail,
    }


def _generate_multilingual_advisory(
    lang: str,
    alert_level: str,
    is_safe: bool,
    weather: Dict[str, Any],
    ocean: Dict[str, Any],
    geofence: Dict[str, Any],
    reasons: List[str],
    lat: float,
    lon: float,
) -> tuple[str, str, str]:
    """Generates localized titles, advisory bodies, and VHF broadcast transcripts."""
    wind = weather.get("wind_speed_knots", 12.0)
    wave = weather.get("wave_height_m", 1.2)
    sea_desc = weather.get("sea_state_description", "Moderate")
    sst = ocean.get("sst_celsius", 28.5)
    chloro = ocean.get("chlorophyll_mg_m3", 0.65)
    pfz_detected = ocean.get("pfz_detected", False)
    species = ocean.get("target_species_recommendations", ["Finfish"])
    imbl_dist = geofence.get("distance_to_imbl_nm", 12.0)
    border_name = geofence.get("nearest_imbl_name", "IMBL")

    # Multilingual Templates
    if lang == "ta":  # Tamil
        if alert_level == "RED":
            title = "⚠️ அவசர எச்சரிக்கை: கடல் பாதுகாப்பு ஆபத்து"
            body = (
                f"கப்பல் நிலை: {lat:.3f}°N, {lon:.3f}°E. சர்வதேச கடல் எல்லைக்கு தூரம்: {imbl_dist} NM.\n"
                f"காரணங்கள்:\n- " + "\n- ".join(reasons) + "\n\n"
                f"பரிந்துரை: மீன்பிடி நடவடிக்கைகளை உடனடியாக நிறுத்திவிட்டு இந்திய கடற்கரை நோக்கி திரும்பவும்."
            )
            audio = f"கவனம்! அவசர எச்சரிக்கை. சர்வதேச எல்லை அருகிலுள்ளது ({imbl_dist} கடல் மைல்) அல்லது கடல் கொந்தளிப்பாக உள்ளது. உடனடியாக கரைக்கு திரும்புங்கள்."
        else:
            title = "✅ கடல்சார் தகவல் & உகந்த மீன்பிடி மண்டல வழிகாட்டல்"
            pfz_text = f"உகந்த மீன்பிடி மண்டலம் (PFZ) கண்டறியப்பட்டது. எதிர்பார்க்கப்படும் மீன் வகைகள்: {', '.join(species[:2])}." if pfz_detected else "சாதாரண மீன்பிடி சூழல்."
            body = (
                f"கடல் நிலைமை: காற்று {wind} knots, அலை உயரம் {wave}m ({sea_desc}).\n"
                f"கடல் மேற்பரப்பு வெப்பநிலை: {sst}°C, குளோரோபில்: {chloro} mg/m³.\n"
                f"{pfz_text}\n"
                f"எல்லை பாதுகாப்பு: {border_name} இலிருந்து {imbl_dist} NM தொலைவில் பாதுகாப்பாக உள்ளீர்கள்."
            )
            audio = f"வணக்கம். தற்போதைய வானிலை சாதகமாக உள்ளது. காற்று {wind} நாட்ஸ், அலை {wave} மீட்டர். எல்லை தூரம் {imbl_dist} கடல் மைல். பாதுகாப்பான பயணம்."
    elif lang == "hi":  # Hindi
        if alert_level == "RED":
            title = "⚠️ आपातकालीन समुद्री चेतावनी: जोखिम अलर्ट"
            body = (
                f"पोत स्थिति: {lat:.3f}°N, {lon:.3f}°E. निकटतम सीमा दूरी: {imbl_dist} NM.\n"
                f"चेतावनी कारण:\n- " + "\n- ".join(reasons) + "\n\n"
                f"कार्रवाई: तुरंत मछली पकड़ना बंद करें और भारतीय तट की ओर लौटें।"
            )
            audio = f"सावधान! आपातकालीन चेतावनी। आप समुद्री सीमा के अत्यंत निकट हैं या मौसम खराब है। तुरंत सुरक्षित बंदरगाह की ओर मुड़ें।"
        else:
            title = "✅ समुद्री सलाह और संभावित मत्स्य पालन क्षेत्र (PFZ)"
            pfz_text = f"संभावित मत्स्य क्षेत्र (PFZ) सक्रिय है। संभावित प्रजातियां: {', '.join(species[:2])}." if pfz_detected else "सामान्य मत्स्य स्थिति।"
            body = (
                f"मौसम: हवा {wind} समुद्री मील/घंटा, लहरें {wave} मी ({sea_desc}).\n"
                f"समुद्र का तापमान: {sst}°C, क्लोरोफिल: {chloro} mg/m³.\n"
                f"{pfz_text}\n"
                f"सीमा सुरक्षा: {border_name} से {imbl_dist} NM की सुरक्षित दूरी पर हैं।"
            )
            audio = f"मौसम सामान्य है। हवा {wind} नॉट्स, लहर {wave} मीटर। सीमा से {imbl_dist} समुद्री मील दूर सुरक्षित हैं।"
    elif lang == "ml":  # Malayalam
        if alert_level == "RED":
            title = "⚠️ അടിയന്തര സമുദ്ര സുരക്ഷാ മുന്നറിയിപ്പ്"
            body = (
                f"ബോട്ട് ലൊക്കേഷൻ: {lat:.3f}°N, {lon:.3f}°E. അതിർത്തി ദൂരം: {imbl_dist} NM.\n"
                f"കാരണങ്ങൾ:\n- " + "\n- ".join(reasons) + "\n\n"
                f"നിർദ്ദേശം: മത്സ്യബന്ധനം നിർത്തി ഉടൻ തീരത്തേക്ക് മടങ്ങുക."
            )
            audio = f"ശ്രദ്ധിക്കുക! അപായ മുന്നറിയിപ്പ്. അതിർത്തിക്ക് വളരെ അടുത്താണ് അല്ലെങ്കിൽ കാറ്റും തിരമാലയും ശക്തമാണ്. ഉടൻ കരയിലേക്ക് മടങ്ങുക."
        else:
            title = "✅ സമുദ്ര ഉപദേശവും മത്സ്യലഭ്യതാ മേഖലയും"
            body = (
                f"കാലാവസ്ഥ: കാറ്റ് {wind} knots, തിരമാല {wave}m.\n"
                f"താപനില: {sst}°C. സാധ്യതയുള്ള മത്സ്യങ്ങൾ: {', '.join(species[:2])}.\n"
                f"അതിർത്തി സുരക്ഷ: {imbl_dist} NM അകലെ സുരക്ഷിതമാണ്."
            )
            audio = f"കാലാവസ്ഥ സുരക്ഷിതമാണ്. കാറ്റ് {wind} നോട്ട്സ്, തിര {wave} മീറ്റർ. അതിർത്തി ദൂരം {imbl_dist} നോട്ടിക്കൽ മൈൽ."
    elif lang == "te":  # Telugu
        if alert_level == "RED":
            title = "⚠️ అత్యవసర సముద్ర భద్రతా హెచ్చరిక"
            body = (
                f"నౌక స్థానం: {lat:.3f}°N, {lon:.3f}°E. సరిహద్దు దూరం: {imbl_dist} NM.\n"
                f"కారణాలు:\n- " + "\n- ".join(reasons) + "\n\n"
                f"చర్య: తక్షణమే చేపల వేట ఆపి భారత తీరానికి తిరిగి వెళ్లండి."
            )
            audio = f"హెచ్చరిక! ప్రమాదకర పరిస్థితులు. సరిహద్దుకు దగ్గరగా ఉన్నారు లేదా వాతావరణం అనుకూలంగా లేదు. వెంటనే తీరానికి రండి."
        else:
            title = "✅ సముద్ర వాతావరణం మరియు మత్స్య జోన్ సమాచారం"
            body = (
                f"వాతావరణం: గాలి {wind} నాట్స్, అలల ఎత్తు {wave} మీ.\n"
                f"ఉష్ణోగ్రత: {sst}°C. చేపల లభ్యత రకాలు: {', '.join(species[:2])}.\n"
                f"సరిహద్దు దూరం: {imbl_dist} NM సురక్షిత ప్రాంతం."
            )
            audio = f"వాతావరణం అనుకూలంగా ఉంది. గాలి {wind} నాట్స్. సరిహద్దు నుండి {imbl_dist} నాటికల్ మైళ్ల దూరంలో ఉన్నారు."
    else:  # English default
        if alert_level == "RED":
            title = "⚠️ CRITICAL MARITIME SAFETY OVERRIDE: CEASE OPERATION"
            body = (
                f"Vessel Position: {lat:.4f}°N, {lon:.4f}°E | Nearest Border: {imbl_dist} NM\n"
                f"SAFETY INTERVENTION REASONS:\n- " + "\n- ".join(reasons) + "\n\n"
                f"MANDATORY DIRECTIVE: All fishing recommendations are SUSPENDED. "
                f"Reverse course immediately and steer towards safe coastal territorial waters."
            )
            audio = (
                f"Security Alert. Vessel at latitude {lat:.2f}, longitude {lon:.2f}. "
                f"Immediate safety override triggered due to proximity to {border_name} "
                f"or hazardous sea state of {wave} meters. Alter heading westward immediately."
            )
        elif alert_level == "YELLOW":
            title = "⚡ MARITIME ADVISORY: CAUTION ADVISED"
            body = (
                f"Conditions: Wind {wind} knots, Waves {wave}m ({sea_desc}).\n"
                f"Notes:\n- " + "\n- ".join(reasons) + "\n\n"
                f"Maintain active radar and VHF channel 16 watch. Nearest boundary is {imbl_dist} NM."
            )
            audio = f"Advisory. Conditions moderate. Wind {wind} knots, wave {wave} meters. Maintain boundary awareness."
        else:
            title = "✅ OPTIMAL MARINE NAVIGATION & PFZ ADVISORY"
            pfz_text = (
                f"Potential Fishing Zone (PFZ) ACTIVE with {round(ocean.get('pfz_confidence', 0.8)*100)}% confidence.\n"
                f"Target Pelagic Species: {', '.join(species)}."
            ) if pfz_detected else "Standard fishing conditions."
            body = (
                f"Marine Weather: Wind {wind} kts, Wave Height {wave}m, Sea State: {sea_desc}.\n"
                f"Oceanography: SST {sst}°C, Chlorophyll {chloro} mg/m³, Current {ocean.get('current_speed_knots')} kts.\n"
                f"{pfz_text}\n"
                f"Geofence Status: SECURE ({imbl_dist} NM from {border_name})."
            )
            audio = (
                f"All clear. Weather is favorable with wind at {wind} knots and waves at {wave} meters. "
                f"Fishing zone confidence is positive. Maintain heading and safe operations."
            )

    return title, body, audio


def _assemble_geojson(
    lat: float,
    lon: float,
    weather: Dict[str, Any],
    ocean: Dict[str, Any],
    geofence: Dict[str, Any],
    alert_level: str,
) -> Dict[str, Any]:
    """Compiles complete GeoJSON FeatureCollection."""
    features = list(geofence.get("geojson_features", []))

    # Add Primary PFZ Polygon feature if detected and safe
    pfz_poly = ocean.get("pfz_polygon_coordinates")
    if pfz_poly and alert_level != "RED":
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [pfz_poly]},
            "properties": {
                "title": "Primary Potential Fishing Zone (PFZ)",
                "fill": "#06B6D4",
                "fill-opacity": 0.35,
                "stroke": "#0891B2",
                "stroke-width": 2,
                "confidence": ocean.get("pfz_confidence", 0.8),
                "species": ocean.get("target_species_recommendations", []),
            },
        })

    # Add AI-derived fishing candidate points if available and safe
    rec_zones = ocean.get("recommended_fishing_zones", [])
    if rec_zones and alert_level != "RED":
        for idx, zone in enumerate(rec_zones):
            z_lat = zone.get("latitude")
            z_lon = zone.get("longitude")
            if z_lat is not None and z_lon is not None:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [z_lon, z_lat]},
                    "properties": {
                        "title": f"Candidate Fishing Zone #{idx + 1}",
                        "distance_km": zone.get("distance_km"),
                        "reason": zone.get("reason"),
                        "marker-color": "#0284C7",
                        "marker-symbol": "star",
                    },
                })

    # Add Safe Buffer Circle / Point
    color_map = {"GREEN": "#10B981", "YELLOW": "#F59E0B", "ORANGE": "#F97316", "RED": "#EF4444"}
    features.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "title": f"Advisory Evaluation Point [{alert_level}]",
            "alert_level": alert_level,
            "marker-color": color_map.get(alert_level, "#10B981"),
            "wave_height_m": weather.get("wave_height_m"),
            "wind_speed_knots": weather.get("wind_speed_knots"),
        },
    })

    return {
        "type": "FeatureCollection",
        "features": features,
    }
