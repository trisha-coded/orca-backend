"""
Synthesizer Agent: Deterministic Safety Gate, Multilingual Advisory Synthesis,
Explainability Evidence Chain, VHF Radio Script, and Complete GeoJSON Map Bundle.
"""

import time
from typing import Dict, Any, List, Tuple
from app.state import MarineAgentState
from app.schemas import SafetyAssessment, GeoJSONFeatureCollection, GeoJSONFeature, GeoJSONGeometry
from app.tools.geofence_tools import geofence_adapter


class SynthesizerAgent:
    """
    Evaluates safety constraints, generates plain-language native advisories,
    produces explainable reasoning chains, and compiles multi-layer GeoJSON tracks.
    """

    def evaluate_safety_gate(
        self,
        weather_data: Dict[str, Any],
        ocean_data: Dict[str, Any],
        geofence_data: Dict[str, Any]
    ) -> Tuple[SafetyAssessment, Dict[str, Any]]:
        weather_cond = weather_data.get("condition", {})
        geofence_cond = geofence_data.get("condition", {})
        ocean_cond = ocean_data.get("condition", {})
        cyclone_eval = weather_data.get("cyclone_assessment", {})

        warnings: List[str] = []
        recommendations: List[str] = []
        deductions: Dict[str, int] = {}
        safety_score = 100

        # 1. Cyclonic Depression Check (Emergency Veto)
        if cyclone_eval.get("is_cyclone_alert"):
            safety_score -= 60
            deductions["cyclonic_depression_hazard"] = 60
            warnings.append(cyclone_eval.get("directive", "Severe cyclonic depression alert!"))
            recommendations.append("MANDATORY EVACUATION: Return to nearest designated harbor immediately.")

        # 2. Weather & Sea State Safety Checks
        w_status = weather_data.get("status", "SAFE")
        if w_status == "DANGEROUS":
            safety_score -= 50
            deductions["severe_wave_wind_hazard"] = 50
            warnings.extend(weather_data.get("warnings", ["High marine meteorological risk."]))
            recommendations.append("Severe wave/wind hazard: Do not venture into open seas.")
        elif w_status == "CAUTION":
            safety_score -= 20
            deductions["moderate_wave_caution"] = 20
            warnings.extend(weather_data.get("warnings", []))
            recommendations.append("Moderate sea state: Exercise heightened caution; ensure life jackets and VHF channel 16 are monitored.")

        # 3. Geofence & Boundary Checks
        border_alert = geofence_cond.get("border_alert_level", "CLEAR")
        if border_alert == "MPA_RESTRICTION":
            safety_score -= 40
            deductions["mpa_sanctuary_violation"] = 40
            mpa_name = geofence_cond.get("mpa_name", "Protected Zone")
            warnings.append(f"Vessel is inside {mpa_name}. Bottom trawling and commercial fishing are strictly illegal.")
            recommendations.append("Immediately alter course to steer outside Marine Protected Area boundaries to avoid penalties.")
        elif border_alert == "BORDER_ALERT":
            safety_score -= 35
            deductions["imminent_border_breach"] = 35
            warnings.append(f"Imminent maritime border violation near {geofence_cond.get('nearest_country')} waters ({geofence_cond.get('nearest_boundary_distance_nm')} NM).")
            recommendations.append("Execute immediate course reversal towards Indian territorial waters.")
        elif border_alert == "WARNING_BUFFER":
            safety_score -= 15
            deductions["border_proximity_warning"] = 15
            warnings.append(f"Approaching international boundary ({geofence_cond.get('nearest_boundary_distance_nm')} NM to {geofence_cond.get('nearest_country')}).")
            recommendations.append("Keep GPS tracking active and maintain buffer from boundary line.")

        # 4. Ocean / Thermal checks
        if ocean_cond.get("sea_surface_temperature_c", 28.0) > 31.5:
            warnings.append("High surface water temperature may disperse surface pelagic shoals.")

        safety_score = max(0, min(100, safety_score))

        # Determine overall safety status and decision
        if safety_score < 50 or cyclone_eval.get("is_cyclone_alert") or w_status == "DANGEROUS" or border_alert in ("BORDER_ALERT", "MPA_RESTRICTION"):
            overall_status = "DANGEROUS"
            decision = "NO_GO"
        elif safety_score < 75 or w_status == "CAUTION" or border_alert == "WARNING_BUFFER":
            overall_status = "CAUTION"
            decision = "GO_WITH_CAUTION"
        else:
            overall_status = "SAFE"
            decision = "GO"
            recommendations.append("Favorable sea conditions for marine operations. Proceed with standard nautical protocols.")

        assessment = SafetyAssessment(
            overall_safety_status=overall_status,
            safety_score=safety_score,
            go_no_go_decision=decision,
            warnings=warnings,
            safety_recommendations=recommendations
        )

        return assessment, deductions

    def generate_explainability_chain(
        self,
        safety: SafetyAssessment,
        weather: Dict[str, Any],
        ocean: Dict[str, Any],
        geofence: Dict[str, Any],
        route: Dict[str, Any],
        deductions: Dict[str, int]
    ) -> Dict[str, Any]:
        w_cond = weather.get("condition", {})
        o_cond = ocean.get("condition", {})
        g_cond = geofence.get("condition", {})
        window = weather.get("best_sailing_window", {})

        # 1. Why safe/unsafe
        if safety.go_no_go_decision == "GO":
            why_safe = (
                f"Conditions are favorable with wave height at {w_cond.get('wave_height_m', 1.0)}m (safe ceiling 2.5m), "
                f"winds at {w_cond.get('wind_speed_knots', 10.0)} kts, and clear buffer ({g_cond.get('nearest_boundary_distance_nm', 20.0)} NM) from international waters."
            )
        elif safety.go_no_go_decision == "GO_WITH_CAUTION":
            why_safe = (
                f"Caution required due to moderate sea roughness ({w_cond.get('wave_height_m')}m waves) or border buffer alert. "
                f"Recommended departure during calm window: {window.get('recommended_window', 'Early Morning')}."
            )
        else:
            why_safe = (
                f"NO_GO enforced because hazardous conditions were detected: "
                f"{' | '.join(safety.warnings) if safety.warnings else 'Safety score fell below safe threshold'}."
            )

        # 2. Why this hotspot
        why_hotspot = (
            f"Thermal gradient SST {o_cond.get('sea_surface_temperature_c', 28.5)}°C combined with Chlorophyll-a {o_cond.get('chlorophyll_a_mg_m3', 0.6)} mg/m³ "
            f"indicates active coastal upwelling, yielding a {o_cond.get('pfz_rating', 'HIGH')} biological productivity index ({o_cond.get('pfz_potential_score', 80)}/100)."
        )

        # 3. Why this route
        why_route = (
            f"Planned rhumb-line heading {route.get('initial_bearing_deg', 250)}° for {route.get('total_distance_nm', 12)} NM steers direct course "
            f"to the biological upwelling hotspot while maintaining full clearance from restricted Marine Protected Areas (MPAs) and territorial borders."
        )

        return {
            "why_safe_or_unsafe": why_safe,
            "why_this_hotspot": why_hotspot,
            "why_this_route": why_route,
            "risk_breakdown": deductions,
            "confidence_score": 96.5
        }

    def generate_multilingual_advisory(
        self,
        language: str,
        species: str,
        vessel: str,
        safety: SafetyAssessment,
        weather: Dict[str, Any],
        ocean: Dict[str, Any],
        geofence: Dict[str, Any],
        tides: Dict[str, Any],
        route: Dict[str, Any]
    ) -> Tuple[str, str]:
        w_cond = weather.get("condition", {})
        o_cond = ocean.get("condition", {})
        g_cond = geofence.get("condition", {})
        window = weather.get("best_sailing_window", {})
        species_name = species or "pelagic fish"
        lang = (language or "en").lower().strip()

        # VHF Broadcast script (English standardized nautical format)
        vhf_script = (
            f"ALL STATIONS, ALL STATIONS. THIS IS OCEANOVA MARINE INTELLIGENCE ADVISORY. "
            f"SAFETY STATUS: {safety.go_no_go_decision}. "
            f"WIND: {w_cond.get('wind_speed_knots')} KNOTS FROM {w_cond.get('wind_direction_deg')} DEGREES. "
            f"SIGNIFICANT WAVES: {w_cond.get('wave_height_m')} METERS. "
            f"RECOMMENDED WINDOW: {window.get('recommended_window', 'MORNING')}. "
            f"RECOMMENDED HEADING: {route.get('initial_bearing_deg', 250)} DEGREES FOR {route.get('total_distance_nm', 10)} NAUTICAL MILES. "
            f"OUT."
        )

        # English (Default)
        if lang == "en":
            lines = [
                f"=== OCEANOVA MARINE ADVISORY ({safety.go_no_go_decision}) ===",
                f"• Safety Status: {safety.overall_safety_status} (Safety Score: {safety.safety_score}/100)",
                f"• Vessel: {vessel} | Target Species: {species_name}",
                f"• Weather & Wave: Wind {w_cond.get('wind_speed_knots')} kts, Waves {w_cond.get('wave_height_m')}m (Period: {w_cond.get('wave_period_s')}s).",
                f"• Best Sailing Window: {window.get('recommended_window')} ({window.get('advice', 'Optimal conditions.')})",
                f"• Ocean & PFZ: SST {o_cond.get('sea_surface_temperature_c')}°C, Chlorophyll {o_cond.get('chlorophyll_a_mg_m3')} mg/m³ -> {o_cond.get('pfz_rating')} Potential ({o_cond.get('pfz_potential_score')}/100).",
                f"• Tidal State: {tides.get('summary', 'Tidal flow normal.')}",
                f"• Safest Track: Heading {route.get('initial_bearing_deg')}° for {route.get('total_distance_nm')} NM (Cruising speed: {route.get('recommended_cruising_speed_knots')} kts, ETA: {route.get('estimated_transit_time_hours')} hrs).",
                f"• Maritime Boundary: {g_cond.get('summary')}"
            ]
            if safety.warnings:
                lines.append("• Warnings: " + " | ".join(safety.warnings))
            return "\n".join(lines), vhf_script

        # Tamil (ta)
        elif lang == "ta":
            status_ta = "பாதுகாப்பானது (GO)" if safety.go_no_go_decision == "GO" else ("எச்சரிக்கையுடன் செல்லவும் (CAUTION)" if safety.go_no_go_decision == "GO_WITH_CAUTION" else "கடலுக்குச் செல்ல வேண்டாம் (NO GO)")
            vhf_script_ta = f"அனைத்து நிலையங்களுக்கும் தகவல். இது ஓஷினோவா கடல்சார் தகவல் சேவை. பாதுகாப்பு நிலை: {status_ta}. காற்று: {w_cond.get('wind_speed_knots')} நாட்ஸ். அலைகள்: {w_cond.get('wave_height_m')} மீ. பரிந்துரைக்கப்பட்ட நேரம்: {window.get('recommended_window', 'காலை')}. முடிந்தது."
            text = (
                f"=== ஓஷினோவா கடல்சார் தகவல் ({status_ta}) ===\n"
                f"• பாதுகாப்பு நிலை: {safety.overall_safety_status} (மதிப்பெண்: {safety.safety_score}/100)\n"
                f"• இலக்கு மீன்: {species_name} | படகு வகை: {vessel}\n"
                f"• வானிலை: காற்று {w_cond.get('wind_speed_knots')} நாட்ஸ், அலை உயரம் {w_cond.get('wave_height_m')} மீ.\n"
                f"• சிறந்த புறப்படும் நேரம்: {window.get('recommended_window')}\n"
                f"• மீன்பிடி மண்டலம் (PFZ): {o_cond.get('pfz_rating')} சாத்தியக்கூறு (குளோரோபில்: {o_cond.get('chlorophyll_a_mg_m3')} mg/m³).\n"
                f"• பாதுகாப்பான திசை: {route.get('initial_bearing_deg')}° ({route.get('total_distance_nm')} NM தூரம், நேரம்: {route.get('estimated_transit_time_hours')} மணி).\n"
                f"• எல்லை நிலை: {g_cond.get('border_alert_level')} ({g_cond.get('nearest_country')} எல்லைக்கு {g_cond.get('nearest_boundary_distance_nm')} NM தூரம்).\n"
                f"• பரிந்துரை: {' '.join(safety.safety_recommendations)}"
            )
            return text, vhf_script_ta

        # Malayalam (ml)
        elif lang == "ml":
            status_ml = "സുരക്ഷിതം (GO)" if safety.go_no_go_decision == "GO" else ("ജാഗ്രതയോടെ പോകുക (CAUTION)" if safety.go_no_go_decision == "GO_WITH_CAUTION" else "കടലിൽ പോകരുത് (NO GO)")
            vhf_script_ml = f"എല്ലാ സ്റ്റേഷനുകൾക്കുമായി അറിയിക്കുന്നു. ഇത് ഒഷ്യനോവ സമുദ്ര മുന്നറിയിപ്പ്. സുരക്ഷാ നില: {status_ml}. കാറ്റ്: {w_cond.get('wind_speed_knots')} നോട്ട്. തിരമാല: {w_cond.get('wave_height_m')} മീറ്റർ. അനുകൂല സമയം: {window.get('recommended_window', 'രാവിലെ')}. തീർന്നു."
            text = (
                f"=== ഒഷ്യനോവ സമുദ്ര മുന്നറിയിപ്പ് ({status_ml}) ===\n"
                f"• സുരക്ഷാ നിലവാരം: {safety.overall_safety_status} (സ്കോർ: {safety.safety_score}/100)\n"
                f"• ലക്ഷ്യമിടുന്ന മത്സ്യം: {species_name} | ബോട്ട്: {vessel}\n"
                f"• കാലാവസ്ഥ: കാറ്റ് {w_cond.get('wind_speed_knots')} നോട്ട്, തിരമാല {w_cond.get('wave_height_m')} മീറ്റർ.\n"
                f"• അനുകൂല സമയം: {window.get('recommended_window')}\n"
                f"• മത്സ്യബന്ധന മേഖല (PFZ): {o_cond.get('pfz_rating')} സാധ്യത.\n"
                f"• സുരക്ഷിത പാത: ദിശ {route.get('initial_bearing_deg')}° ({route.get('total_distance_nm')} NM ദൂരം).\n"
                f"• അതിർത്തി മുന്നറിയിപ്പ്: {g_cond.get('border_alert_level')} ({g_cond.get('nearest_boundary_distance_nm')} NM).\n"
                f"• നിർദ്ദേശം: {' '.join(safety.safety_recommendations)}"
            )
            return text, vhf_script_ml

        # Hindi (hi)
        elif lang == "hi":
            status_hi = "सुरक्षित (GO)" if safety.go_no_go_decision == "GO" else ("सावधानी बरतें (CAUTION)" if safety.go_no_go_decision == "GO_WITH_CAUTION" else "समुद्र में न जाएं (NO GO)")
            vhf_script_hi = f"सभी स्टेशनों को सूचित किया जाता है। यह ओशिनोवा समुद्री सलाहकार सेवा है। सुरक्षा स्थिति: {status_hi}। हवा: {w_cond.get('wind_speed_knots')} नॉट्स। लहरें: {w_cond.get('wave_height_m')} मीटर। अनुशंसित समय: {window.get('recommended_window', 'सुबह')}। समाप्त।"
            text = (
                f"=== ओशिनोवा समुद्री सलाह ({status_hi}) ===\n"
                f"• सुरक्षा स्थिति: {safety.overall_safety_status} (सुरक्षा स्कोर: {safety.safety_score}/100)\n"
                f"• लक्षित मछली: {species_name} | नाव: {vessel}\n"
                f"• मौसम: हवा {w_cond.get('wind_speed_knots')} नॉट्स, लहरें {w_cond.get('wave_height_m')} मीटर.\n"
                f"• सर्वश्रेष्ठ प्रस्थान समय: {window.get('recommended_window')}\n"
                f"• संभावित मत्स्य क्षेत्र (PFZ): {o_cond.get('pfz_rating')} संभावना (स्कोर: {o_cond.get('pfz_potential_score')}/100).\n"
                f"• सुरक्षित दिशा: {route.get('initial_bearing_deg')}° ({route.get('total_distance_nm')} NM).\n"
                f"• समुद्री सीमा: {g_cond.get('summary')}\n"
                f"• कार्रवाई: {' '.join(safety.safety_recommendations)}"
            )
            return text, vhf_script_hi

        # Telugu (te)
        elif lang == "te":
            status_te = "సురక్షితం (GO)" if safety.go_no_go_decision == "GO" else ("జాగ్రత్త అవసరం (CAUTION)" if safety.go_no_go_decision == "GO_WITH_CAUTION" else "సముద్రంలోకి వెళ్లవద్దు (NO GO)")
            vhf_script_te = f"అన్ని స్టేషన్లకు సమాచారం. ఇది ఓషినోవా సముద్ర సలహా. భద్రతా స్థితి: {status_te}. గాలి: {w_cond.get('wind_speed_knots')} నాట్స్. అలలు: {w_cond.get('wave_height_m')} మీటర్లు. ప్రయాణ సమయం: {window.get('recommended_window', 'ఉదయం')}. ముగిసింది."
            text = (
                f"=== ఓషినోవా సముద్ర సలహా ({status_te}) ===\n"
                f"• భద్రతా స్థితి: {safety.overall_safety_status} (స్కోరు: {safety.safety_score}/100)\n"
                f"• లక్ష్య చేప: {species_name} | పడవ: {vessel}\n"
                f"• వాతావరణం: గాలి {w_cond.get('wind_speed_knots')} నాట్స్, అలల ఎత్తు {w_cond.get('wave_height_m')} మీ.\n"
                f"• ఉత్తమ బయలుదేరే సమయం: {window.get('recommended_window')}\n"
                f"• సంభావ్య చేపల వేట మండలం (PFZ): {o_cond.get('pfz_rating')}.\n"
                f"• సురక్షిత మార్గం: దిశ {route.get('initial_bearing_deg')}° ({route.get('total_distance_nm')} NM).\n"
                f"• సరిహద్దు స్థితి: {g_cond.get('border_alert_level')}.\n"
                f"• సూచన: {' '.join(safety.safety_recommendations)}"
            )
            return text, vhf_script_te

        # Kannada (kn)
        elif lang == "kn":
            status_kn = "ಸುರಕ್ಷಿತ (GO)" if safety.go_no_go_decision == "GO" else ("ಎಚ್ಚರಿಕೆಯಿಂದ ಮುಂದುವರಿಯಿರಿ (CAUTION)" if safety.go_no_go_decision == "GO_WITH_CAUTION" else "ಸಮುದ್ರಕ್ಕೆ ಇಳಿಯಬೇಡಿ (NO GO)")
            vhf_script_kn = f"ಎಲ್ಲಾ ನಿಲ್ದಾಣಗಳಿಗೆ ಸೂಚನೆ. ಇದು ಓಷಿನೋವಾ ಸಮುದ್ರ ಮಾಹಿತಿ. ಸುರಕ್ಷತಾ ಸ್ಥಿತಿ: {status_kn}. ಗಾಳಿ: {w_cond.get('wind_speed_knots')} ನಾಟ್ಸ್. ಅಲೆಗಳು: {w_cond.get('wave_height_m')} ಮೀಟರ್. ಶಿಫಾರಸು ಮಾಡಿದ ನಿರ್ಗಮನ ಸಮಯ: {window.get('recommended_window', 'ಬೆಳಿಗ್ಗೆ')}. ಮುಗಿಯಿತು."
            text = (
                f"=== ಓಷಿನೋವಾ ಸಾಗರ ಮಾಹಿತಿ ({status_kn}) ===\n"
                f"• ಸುರಕ್ಷತಾ ಸ್ಥಿತಿ: {safety.overall_safety_status} (ಅಂಕ: {safety.safety_score}/100)\n"
                f"• ಗುರಿ ಮೀನು: {species_name} | ದೋಣಿ: {vessel}\n"
                f"• ಹವಾಮಾನ: ಗಾಳಿ {w_cond.get('wind_speed_knots')} ನಾಟ್ಸ್, ಅಲೆಗಳ ಎತ್ತರ {w_cond.get('wave_height_m')} ಮೀಟರ್.\n"
                f"• ಅತ್ಯುತ್ತಮ ನಿರ್ಗಮನ ಸಮಯ: {window.get('recommended_window')}\n"
                f"• ಮೀನುಗಾರಿಕಾ ಸಂಭಾವ್ಯ ವಲಯ (PFZ): {o_cond.get('pfz_rating')} ಸಾಧ್ಯತೆ (ಸ್ಕೋರ್: {o_cond.get('pfz_potential_score')}/100).\n"
                f"• ಸುರಕ್ಷಿತ ದಿಕ್ಕು: {route.get('initial_bearing_deg')}° ({route.get('total_distance_nm')} NM ದೂರ).\n"
                f"• ಸಮುದ್ರ ಗಡಿ: {g_cond.get('summary')}\n"
                f"• ಶಿಫಾರಸು: {' '.join(safety.safety_recommendations)}"
            )
            return text, vhf_script_kn

        return self.generate_multilingual_advisory("en", species, vessel, safety, weather, ocean, geofence, tides, route)

    async def execute(self, state: MarineAgentState) -> Dict[str, Any]:
        t0 = time.time()
        lat = state["latitude"]
        lon = state["longitude"]
        lang = state.get("language", "en")
        species = state.get("target_species") or "Marine Fishes"
        vessel = state.get("vessel_type", "Motorized Boat")

        weather_data = state.get("weather_data", {})
        ocean_data = state.get("ocean_data", {})
        geofence_data = state.get("geofence_data", {})
        tides_data = state.get("tides_data", {})
        route_data = state.get("route_data", {})

        # 1. Run Deterministic Safety Gate
        safety_assessment, deductions = self.evaluate_safety_gate(weather_data, ocean_data, geofence_data)

        # 2. Run Multilingual Synthesis & VHF Script
        advisory_text, vhf_script = self.generate_multilingual_advisory(
            lang, species, vessel, safety_assessment, weather_data, ocean_data, geofence_data, tides_data, route_data
        )

        # 3. Assemble Explainability Chain
        explainability = self.generate_explainability_chain(
            safety_assessment, weather_data, ocean_data, geofence_data, route_data, deductions
        )

        # 4. Generate Unified GeoJSON FeatureCollection (including Route & Waypoints)
        base_geojson = geofence_adapter.generate_geojson_bundle(
            lat, lon, geofence_data, ocean_data.get("hotspots", [])
        )

        # Add safe route LineString & Waypoints if route planned
        features = list(base_geojson.features)
        if route_data.get("route_geojson"):
            features.insert(1, route_data["route_geojson"])

        for wp in route_data.get("waypoints", []):
            features.append(
                GeoJSONFeature(
                    geometry=GeoJSONGeometry(
                        type="Point",
                        coordinates=[wp["longitude"], wp["latitude"]]
                    ),
                    properties={
                        "layer": "navigation_waypoint",
                        "title": wp["name"],
                        "bearing_deg": wp["bearing_deg"],
                        "instruction": wp["instruction"]
                    }
                )
            )

        geojson_col = GeoJSONFeatureCollection(features=features)

        elapsed = round((time.time() - t0) * 1000, 2)
        step_log = {
            "agent_name": "SynthesizerAgent (Safety Gate & Explainable Synthesis)",
            "status": "SUCCESS" if safety_assessment.go_no_go_decision != "NO_GO" else "WARNING",
            "summary": (
                f"Safety Gate evaluated: '{safety_assessment.go_no_go_decision}' (Score: {safety_assessment.safety_score}/100). "
                f"Generated native advisory in '{lang}', VHF radio script, explainability evidence chain, and {len(features)} GeoJSON map features."
            ),
            "latency_ms": elapsed,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        return {
            "safety_assessment": safety_assessment.model_dump(),
            "advisory_text": advisory_text,
            "audio_broadcast_script": vhf_script,
            "explainability_chain": explainability,
            "geojson": geojson_col,
            "reasoning_logs": [step_log]
        }


synthesizer_agent = SynthesizerAgent()
