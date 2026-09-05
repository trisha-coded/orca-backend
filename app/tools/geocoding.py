"""
Indian Coastal Ports & Maritime Geocoding Engine.
Provides high-precision coordinate resolution for 100+ Indian coastal ports,
fishing harbors, landing centers, and coastal districts with Nominatim live fallback.
"""

import re
from typing import Dict, Any, Optional, Tuple

try:
    import httpx
except ImportError:
    httpx = None


# High-precision coordinates for Indian maritime coastal ports and landing centers
INDIAN_COASTAL_LOCATIONS: Dict[str, Dict[str, Any]] = {
    # Regional Indian Language Maritime Harbor Aliases (Kannada, Hindi, Tamil, Malayalam, Telugu)
    "ಮಂಗಳೂರು": {"lat": 12.9141, "lon": 74.8560, "state": "Karnataka", "type": "Major Port & Old Harbor", "region": "Central Arabian Sea (Canara Coast)"},
    "ಮಂಗಳೂರು ಬಂದರು": {"lat": 12.9141, "lon": 74.8560, "state": "Karnataka", "type": "Major Port", "region": "Central Arabian Sea (Canara Coast)"},
    "ಮಂಗಳೂರಿನಲ್ಲಿ": {"lat": 12.9141, "lon": 74.8560, "state": "Karnataka", "type": "Major Port", "region": "Central Arabian Sea (Canara Coast)"},
    "ಮಂಗಳೂರು ಬಳಿ": {"lat": 12.9141, "lon": 74.8560, "state": "Karnataka", "type": "Major Port", "region": "Central Arabian Sea (Canara Coast)"},
    "ಮಾಲ್ಪೆ": {"lat": 13.3510, "lon": 74.7040, "state": "Karnataka", "type": "Fishing Harbor", "region": "Central Arabian Sea (Canara Coast)"},
    "ಕಾರವಾರ": {"lat": 14.8150, "lon": 74.1300, "state": "Karnataka", "type": "Fishing Harbor", "region": "Central Arabian Sea (Canara Coast)"},
    "ಕೊಚ್ಚಿನ್": {"lat": 9.9312, "lon": 76.2673, "state": "Kerala", "type": "Major Port", "region": "South Arabian Sea (Malabar Coast)"},
    "ಕೊಚ್ಚಿ": {"lat": 9.9312, "lon": 76.2673, "state": "Kerala", "type": "Major Port", "region": "South Arabian Sea (Malabar Coast)"},
    "ಗೋವಾ": {"lat": 15.4056, "lon": 73.8043, "state": "Goa", "type": "Major Port", "region": "Central Arabian Sea (Konkan Coast)"},
    "ಮುಂಬೈ": {"lat": 18.9220, "lon": 72.8347, "state": "Maharashtra", "type": "Major Port", "region": "North Arabian Sea (Maharashtra Coast)"},
    "ವೆರಾವಲ್": {"lat": 20.9000, "lon": 70.3667, "state": "Gujarat", "type": "Major Port", "region": "North Arabian Sea (Saurashtra Coast)"},
    "ಪೋರಬಂದರ್": {"lat": 21.6417, "lon": 69.6293, "state": "Gujarat", "type": "Major Port", "region": "North Arabian Sea (Saurashtra Coast)"},
    "ರಾಮೇಶ್ವರಂ": {"lat": 9.2876, "lon": 79.3129, "state": "Tamil Nadu", "type": "Fishing Harbor", "region": "Gulf of Mannar / Palk Strait"},
    "ಚೆನ್ನೈ": {"lat": 13.0827, "lon": 80.2707, "state": "Tamil Nadu", "type": "Major Port", "region": "Central Bay of Bengal (Coromandel Coast)"},
    "ಕನ್ಯಾಕುಮಾರಿ": {"lat": 8.0883, "lon": 77.5385, "state": "Tamil Nadu", "type": "Cape", "region": "Indian Ocean Cape"},
    "ವಿಶಾಖಪಟ್ಟಣಂ": {"lat": 17.6868, "lon": 83.2185, "state": "Andhra Pradesh", "type": "Major Port", "region": "Central Bay of Bengal"},
    "ಪಾರದೀಪ್": {"lat": 20.3167, "lon": 86.6167, "state": "Odisha", "type": "Major Port", "region": "North Bay of Bengal"},
    "ಕೋಲ್ಕತ್ತಾ": {"lat": 22.0294, "lon": 88.0645, "state": "West Bengal", "type": "Major Port", "region": "North Bay of Bengal"},

    # Hindi
    "मैंगलोर": {"lat": 12.9141, "lon": 74.8560, "state": "Karnataka", "type": "Major Port & Old Harbor", "region": "Central Arabian Sea (Canara Coast)"},
    "मंगलुरु": {"lat": 12.9141, "lon": 74.8560, "state": "Karnataka", "type": "Major Port", "region": "Central Arabian Sea (Canara Coast)"},
    "मालपे": {"lat": 13.3510, "lon": 74.7040, "state": "Karnataka", "type": "Fishing Harbor", "region": "Central Arabian Sea (Canara Coast)"},
    "कारवार": {"lat": 14.8150, "lon": 74.1300, "state": "Karnataka", "type": "Fishing Harbor", "region": "Central Arabian Sea (Canara Coast)"},
    "कोचीन": {"lat": 9.9312, "lon": 76.2673, "state": "Kerala", "type": "Major Port", "region": "South Arabian Sea (Malabar Coast)"},
    "कोच्चि": {"lat": 9.9312, "lon": 76.2673, "state": "Kerala", "type": "Major Port", "region": "South Arabian Sea (Malabar Coast)"},
    "गोवा": {"lat": 15.4056, "lon": 73.8043, "state": "Goa", "type": "Major Port", "region": "Central Arabian Sea (Konkan Coast)"},
    "मुंबई": {"lat": 18.9220, "lon": 72.8347, "state": "Maharashtra", "type": "Major Port", "region": "North Arabian Sea (Maharashtra Coast)"},
    "वेरावल": {"lat": 20.9000, "lon": 70.3667, "state": "Gujarat", "type": "Major Port", "region": "North Arabian Sea (Saurashtra Coast)"},
    "पोरबंदर": {"lat": 21.6417, "lon": 69.6293, "state": "Gujarat", "type": "Major Port", "region": "North Arabian Sea (Saurashtra Coast)"},
    "रामेश्वरम": {"lat": 9.2876, "lon": 79.3129, "state": "Tamil Nadu", "type": "Fishing Harbor", "region": "Gulf of Mannar / Palk Strait"},
    "चेन्नई": {"lat": 13.0827, "lon": 80.2707, "state": "Tamil Nadu", "type": "Major Port", "region": "Central Bay of Bengal"},
    "कन्याकुमारी": {"lat": 8.0883, "lon": 77.5385, "state": "Tamil Nadu", "type": "Cape", "region": "Indian Ocean Cape"},
    "विशाखापत्तनम": {"lat": 17.6868, "lon": 83.2185, "state": "Andhra Pradesh", "type": "Major Port", "region": "Central Bay of Bengal"},
    "पारादीप": {"lat": 20.3167, "lon": 86.6167, "state": "Odisha", "type": "Major Port", "region": "North Bay of Bengal"},
    "कोलकाता": {"lat": 22.0294, "lon": 88.0645, "state": "West Bengal", "type": "Major Port", "region": "North Bay of Bengal"},

    # Tamil
    "மங்களூர்": {"lat": 12.9141, "lon": 74.8560, "state": "Karnataka", "type": "Major Port", "region": "Central Arabian Sea (Canara Coast)"},
    "மங்களூரு": {"lat": 12.9141, "lon": 74.8560, "state": "Karnataka", "type": "Major Port", "region": "Central Arabian Sea (Canara Coast)"},
    "மால்பே": {"lat": 13.3510, "lon": 74.7040, "state": "Karnataka", "type": "Fishing Harbor", "region": "Central Arabian Sea (Canara Coast)"},
    "கார்வார்": {"lat": 14.8150, "lon": 74.1300, "state": "Karnataka", "type": "Fishing Harbor", "region": "Central Arabian Sea (Canara Coast)"},
    "கொச்சின்": {"lat": 9.9312, "lon": 76.2673, "state": "Kerala", "type": "Major Port", "region": "South Arabian Sea (Malabar Coast)"},
    "கொச்சி": {"lat": 9.9312, "lon": 76.2673, "state": "Kerala", "type": "Major Port", "region": "South Arabian Sea (Malabar Coast)"},
    "கோவா": {"lat": 15.4056, "lon": 73.8043, "state": "Goa", "type": "Major Port", "region": "Central Arabian Sea"},
    "மும்பை": {"lat": 18.9220, "lon": 72.8347, "state": "Maharashtra", "type": "Major Port", "region": "North Arabian Sea"},
    "வேராவல்": {"lat": 20.9000, "lon": 70.3667, "state": "Gujarat", "type": "Major Port", "region": "North Arabian Sea"},
    "ராமேஸ்வரம்": {"lat": 9.2876, "lon": 79.3129, "state": "Tamil Nadu", "type": "Fishing Harbor", "region": "Gulf of Mannar / Palk Strait"},
    "சென்னை": {"lat": 13.0827, "lon": 80.2707, "state": "Tamil Nadu", "type": "Major Port", "region": "Central Bay of Bengal"},
    "கன்னியாகுமரி": {"lat": 8.0883, "lon": 77.5385, "state": "Tamil Nadu", "type": "Cape", "region": "Indian Ocean Cape"},
    "விசாகப்பட்டினம்": {"lat": 17.6868, "lon": 83.2185, "state": "Andhra Pradesh", "type": "Major Port", "region": "Central Bay of Bengal"},

    # Malayalam
    "മംഗലാപുരം": {"lat": 12.9141, "lon": 74.8560, "state": "Karnataka", "type": "Major Port", "region": "Central Arabian Sea (Canara Coast)"},
    "മാൽപെ": {"lat": 13.3510, "lon": 74.7040, "state": "Karnataka", "type": "Fishing Harbor", "region": "Central Arabian Sea (Canara Coast)"},
    "കാർവാർ": {"lat": 14.8150, "lon": 74.1300, "state": "Karnataka", "type": "Fishing Harbor", "region": "Central Arabian Sea (Canara Coast)"},
    "കൊച്ചിൻ": {"lat": 9.9312, "lon": 76.2673, "state": "Kerala", "type": "Major Port", "region": "South Arabian Sea (Malabar Coast)"},
    "കൊച്ചി": {"lat": 9.9312, "lon": 76.2673, "state": "Kerala", "type": "Major Port", "region": "South Arabian Sea (Malabar Coast)"},
    "ബേപ്പൂർ": {"lat": 11.1640, "lon": 75.8080, "state": "Kerala", "type": "Major Fishing Harbor", "region": "South Arabian Sea (Malabar Coast)"},
    "കോഴിക്കോട്": {"lat": 11.2588, "lon": 75.7804, "state": "Kerala", "type": "Port Town", "region": "South Arabian Sea (Malabar Coast)"},
    "ഗോവ": {"lat": 15.4056, "lon": 73.8043, "state": "Goa", "type": "Major Port", "region": "Central Arabian Sea"},
    "മുംബൈ": {"lat": 18.9220, "lon": 72.8347, "state": "Maharashtra", "type": "Major Port", "region": "North Arabian Sea"},
    "വേരാവൽ": {"lat": 20.9000, "lon": 70.3667, "state": "Gujarat", "type": "Major Port", "region": "North Arabian Sea"},
    "രാമേശ്വരം": {"lat": 9.2876, "lon": 79.3129, "state": "Tamil Nadu", "type": "Fishing Harbor", "region": "Gulf of Mannar / Palk Strait"},
    "ചെന്നൈ": {"lat": 13.0827, "lon": 80.2707, "state": "Tamil Nadu", "type": "Major Port", "region": "Central Bay of Bengal"},
    "കന്യാകുമാരി": {"lat": 8.0883, "lon": 77.5385, "state": "Tamil Nadu", "type": "Cape", "region": "Indian Ocean Cape"},

    # Telugu
    "మంగళూరు": {"lat": 12.9141, "lon": 74.8560, "state": "Karnataka", "type": "Major Port", "region": "Central Arabian Sea"},
    "మాల్పే": {"lat": 13.3510, "lon": 74.7040, "state": "Karnataka", "type": "Fishing Harbor", "region": "Central Arabian Sea"},
    "కార్వార్": {"lat": 14.8150, "lon": 74.1300, "state": "Karnataka", "type": "Fishing Harbor", "region": "Central Arabian Sea"},
    "కొచ్చిన్": {"lat": 9.9312, "lon": 76.2673, "state": "Kerala", "type": "Major Port", "region": "South Arabian Sea"},
    "కొచ్చి": {"lat": 9.9312, "lon": 76.2673, "state": "Kerala", "type": "Major Port", "region": "South Arabian Sea"},
    "గోవా": {"lat": 15.4056, "lon": 73.8043, "state": "Goa", "type": "Major Port", "region": "Central Arabian Sea"},
    "ముంబై": {"lat": 18.9220, "lon": 72.8347, "state": "Maharashtra", "type": "Major Port", "region": "North Arabian Sea"},
    "వెరావల్": {"lat": 20.9000, "lon": 70.3667, "state": "Gujarat", "type": "Major Port", "region": "North Arabian Sea"},
    "రామేశ్వరం": {"lat": 9.2876, "lon": 79.3129, "state": "Tamil Nadu", "type": "Fishing Harbor", "region": "Gulf of Mannar / Palk Strait"},
    "చెన్నై": {"lat": 13.0827, "lon": 80.2707, "state": "Tamil Nadu", "type": "Major Port", "region": "Central Bay of Bengal"},
    "కన్యాకుమారి": {"lat": 8.0883, "lon": 77.5385, "state": "Tamil Nadu", "type": "Cape", "region": "Indian Ocean Cape"},
    "విశాఖపట్నం": {"lat": 17.6868, "lon": 83.2185, "state": "Andhra Pradesh", "type": "Major Port", "region": "Central Bay of Bengal"},
    "పారదీప్": {"lat": 20.3167, "lon": 86.6167, "state": "Odisha", "type": "Major Port", "region": "North Bay of Bengal"},
    "కోల్‌కతా": {"lat": 22.0294, "lon": 88.0645, "state": "West Bengal", "type": "Major Port", "region": "North Bay of Bengal"},
    # Kerala
    "cochin": {"lat": 9.9312, "lon": 76.2673, "state": "Kerala", "type": "Major Port & Fishing Harbor", "region": "South Arabian Sea (Malabar Coast)"},
    "kochi": {"lat": 9.9312, "lon": 76.2673, "state": "Kerala", "type": "Major Port", "region": "South Arabian Sea (Malabar Coast)"},
    "kollam": {"lat": 8.8932, "lon": 76.6141, "state": "Kerala", "type": "Neendakara Fishing Harbor", "region": "South Arabian Sea (Malabar Coast)"},
    "neendakara": {"lat": 8.9412, "lon": 76.5412, "state": "Kerala", "type": "Major Fishing Harbor", "region": "South Arabian Sea (Malabar Coast)"},
    "vizhinjam": {"lat": 8.3750, "lon": 76.9920, "state": "Kerala", "type": "Deep Sea Transshipment Port", "region": "South Arabian Sea (Malabar Coast)"},
    "trivandrum": {"lat": 8.5241, "lon": 76.9366, "state": "Kerala", "type": "Coastal Capital", "region": "South Arabian Sea (Malabar Coast)"},
    "thiruvananthapuram": {"lat": 8.5241, "lon": 76.9366, "state": "Kerala", "type": "Coastal Capital", "region": "South Arabian Sea (Malabar Coast)"},
    "munambam": {"lat": 10.1850, "lon": 76.1680, "state": "Kerala", "type": "Major Fishing Harbor", "region": "South Arabian Sea (Malabar Coast)"},
    "kozhikode": {"lat": 11.2588, "lon": 75.7804, "state": "Kerala", "type": "Beypore Fishing Harbor", "region": "South Arabian Sea (Malabar Coast)"},
    "calicut": {"lat": 11.2588, "lon": 75.7804, "state": "Kerala", "type": "Port Town", "region": "South Arabian Sea (Malabar Coast)"},
    "beypore": {"lat": 11.1640, "lon": 75.8080, "state": "Kerala", "type": "Major Fishing Harbor", "region": "South Arabian Sea (Malabar Coast)"},
    "kannur": {"lat": 11.8745, "lon": 75.3704, "state": "Kerala", "type": "Fishing Harbor (Mopla Bay)", "region": "South Arabian Sea (Malabar Coast)"},
    "kasaragod": {"lat": 12.4996, "lon": 74.9869, "state": "Kerala", "type": "Coastal Town", "region": "South Arabian Sea (Malabar Coast)"},

    # Karnataka
    "mangalore": {"lat": 12.9141, "lon": 74.8560, "state": "Karnataka", "type": "New Mangalore Port & Old Harbor", "region": "Central Arabian Sea (Canara Coast)"},
    "mangaluru": {"lat": 12.9141, "lon": 74.8560, "state": "Karnataka", "type": "Major Port", "region": "Central Arabian Sea (Canara Coast)"},
    "malpe": {"lat": 13.3510, "lon": 74.7040, "state": "Karnataka", "type": "Premier Deep Sea Trawler Harbor", "region": "Central Arabian Sea (Canara Coast)"},
    "udupi": {"lat": 13.3409, "lon": 74.7421, "state": "Karnataka", "type": "Coastal District", "region": "Central Arabian Sea (Canara Coast)"},
    "gangolli": {"lat": 13.6420, "lon": 74.6730, "state": "Karnataka", "type": "Fishing Harbor", "region": "Central Arabian Sea (Canara Coast)"},
    "bhatkal": {"lat": 13.9800, "lon": 74.5500, "state": "Karnataka", "type": "Fishing Port", "region": "Central Arabian Sea (Canara Coast)"},
    "honnavar": {"lat": 14.2800, "lon": 74.4500, "state": "Karnataka", "type": "Fishing Harbor", "region": "Central Arabian Sea (Canara Coast)"},
    "tadadi": {"lat": 14.5240, "lon": 74.3640, "state": "Karnataka", "type": "Fishing Harbor", "region": "Central Arabian Sea (Canara Coast)"},
    "karwar": {"lat": 14.8150, "lon": 74.1300, "state": "Karnataka", "type": "Baithkol Harbor & Naval Base", "region": "Central Arabian Sea (Canara Coast)"},

    # Karnataka
    "karnataka": {"lat": 12.9141, "lon": 74.8560, "state": "Karnataka", "type": "Coastal State", "region": "Central Arabian Sea (Canara Coast)"},

    # Goa
    "goa": {"lat": 15.4056, "lon": 73.8043, "state": "Goa", "type": "Major Port & Coastal Sector", "region": "Central Arabian Sea (Konkan Coast)"},
    "panaji": {"lat": 15.4909, "lon": 73.8278, "state": "Goa", "type": "State Capital & Port", "region": "Central Arabian Sea (Konkan Coast)"},
    "mormugao": {"lat": 15.4167, "lon": 73.8000, "state": "Goa", "type": "Major Port", "region": "Central Arabian Sea (Konkan Coast)"},
    "vasco": {"lat": 15.3959, "lon": 73.8157, "state": "Goa", "type": "Port Town", "region": "Central Arabian Sea (Konkan Coast)"},
    "betul": {"lat": 15.1480, "lon": 73.9620, "state": "Goa", "type": "Fishing Harbor", "region": "Central Arabian Sea (Konkan Coast)"},
    "malvan": {"lat": 16.0600, "lon": 73.4600, "state": "Maharashtra", "type": "Konkan Fishing Center", "region": "Central Arabian Sea (Konkan Coast)"},

    # Kerala
    "kerala": {"lat": 9.9312, "lon": 76.2673, "state": "Kerala", "type": "Coastal State", "region": "South Arabian Sea (Malabar Coast)"},

    # Maharashtra
    "mumbai": {"lat": 18.9220, "lon": 72.8347, "state": "Maharashtra", "type": "Sassoon Dock & Ferry Wharf", "region": "North Arabian Sea (Maharashtra Coast)"},
    "bombay": {"lat": 18.9220, "lon": 72.8347, "state": "Maharashtra", "type": "Sassoon Dock", "region": "North Arabian Sea (Maharashtra Coast)"},
    "sassoon dock": {"lat": 18.9130, "lon": 72.8240, "state": "Maharashtra", "type": "Historic Fishing Harbor", "region": "North Arabian Sea (Maharashtra Coast)"},
    "bhaucha dhakka": {"lat": 18.9560, "lon": 72.8520, "state": "Maharashtra", "type": "Ferry Wharf Fishing Center", "region": "North Arabian Sea (Maharashtra Coast)"},
    "ratnagiri": {"lat": 16.9902, "lon": 73.3120, "state": "Maharashtra", "type": "Mirkarwada Fishing Harbor", "region": "North Arabian Sea (Maharashtra Coast)"},
    "alibag": {"lat": 18.6414, "lon": 72.8722, "state": "Maharashtra", "type": "Coastal Town", "region": "North Arabian Sea (Maharashtra Coast)"},
    "palghar": {"lat": 19.6967, "lon": 72.7699, "state": "Maharashtra", "type": "Satpati Fishing Harbor", "region": "North Arabian Sea (Maharashtra Coast)"},
    "satpati": {"lat": 19.7333, "lon": 72.7000, "state": "Maharashtra", "type": "Major Fishing Village", "region": "North Arabian Sea (Maharashtra Coast)"},
    "dahanu": {"lat": 19.9700, "lon": 72.7300, "state": "Maharashtra", "type": "Fishing Harbor", "region": "North Arabian Sea (Maharashtra Coast)"},

    # Gujarat
    "veraval": {"lat": 20.9000, "lon": 70.3667, "state": "Gujarat", "type": "Asia's Largest Fishing Harbor", "region": "North Arabian Sea (Saurashtra Coast)"},
    "porbandar": {"lat": 21.6417, "lon": 69.6293, "state": "Gujarat", "type": "Major Fishing Port", "region": "North Arabian Sea (Saurashtra Coast)"},
    "mangrol": {"lat": 21.1200, "lon": 70.1200, "state": "Gujarat", "type": "Fishing Harbor", "region": "North Arabian Sea (Saurashtra Coast)"},
    "okha": {"lat": 22.4667, "lon": 69.0667, "state": "Gujarat", "type": "Gulf of Kutch Port", "region": "North Arabian Sea (Gujarat Coast)"},
    "kandla": {"lat": 23.0000, "lon": 70.2167, "state": "Gujarat", "type": "Deendayal Major Port", "region": "North Arabian Sea (Gulf of Kutch)"},
    "mundra": {"lat": 22.8333, "lon": 69.7000, "state": "Gujarat", "type": "Commercial Deep Water Port", "region": "North Arabian Sea (Gulf of Kutch)"},
    "jafarabad": {"lat": 20.8700, "lon": 71.3700, "state": "Gujarat", "type": "Major Trawler Harbor (Bombay Duck)", "region": "North Arabian Sea (Saurashtra Coast)"},
    "alang": {"lat": 21.4100, "lon": 72.1800, "state": "Gujarat", "type": "Gulf of Khambhat", "region": "North Arabian Sea (Gulf of Khambhat)"},

    # Tamil Nadu
    "chennai": {"lat": 13.0827, "lon": 80.2707, "state": "Tamil Nadu", "type": "Kasimedu Fishing Harbor", "region": "Central Bay of Bengal (Coromandel Coast)"},
    "madras": {"lat": 13.0827, "lon": 80.2707, "state": "Tamil Nadu", "type": "Major Port", "region": "Central Bay of Bengal (Coromandel Coast)"},
    "kasimedu": {"lat": 13.1230, "lon": 80.2980, "state": "Tamil Nadu", "type": "Major Chennai Fishing Harbor", "region": "Central Bay of Bengal (Coromandel Coast)"},
    "cuddalore": {"lat": 11.7500, "lon": 79.7700, "state": "Tamil Nadu", "type": "Fishing Harbor", "region": "Central Bay of Bengal (Coromandel Coast)"},
    "nagapattinam": {"lat": 10.7670, "lon": 79.8420, "state": "Tamil Nadu", "type": "Major Trawler Harbor", "region": "Central Bay of Bengal (Coromandel Coast)"},
    "rameswaram": {"lat": 9.2876, "lon": 79.3129, "state": "Tamil Nadu", "type": "Palk Bay & Gulf of Mannar Gateway", "region": "Gulf of Mannar / Palk Strait"},
    "dhanushkodi": {"lat": 9.1780, "lon": 79.4180, "state": "Tamil Nadu", "type": "Palk Strait Border Point", "region": "Gulf of Mannar / Palk Strait"},
    "pamban": {"lat": 9.2800, "lon": 79.2100, "state": "Tamil Nadu", "type": "Pamban Channel Harbor", "region": "Gulf of Mannar / Palk Strait"},
    "mandapam": {"lat": 9.2780, "lon": 79.1240, "state": "Tamil Nadu", "type": "Gulf of Mannar Fishing Center", "region": "Gulf of Mannar / Palk Strait"},
    "tuticorin": {"lat": 8.7642, "lon": 78.1348, "state": "Tamil Nadu", "type": "V.O. Chidambaranar Major Port", "region": "Gulf of Mannar (Coromandel South)"},
    "thoothukudi": {"lat": 8.7642, "lon": 78.1348, "state": "Tamil Nadu", "type": "Major Harbor", "region": "Gulf of Mannar (Coromandel South)"},
    "kanyakumari": {"lat": 8.0883, "lon": 77.5385, "state": "Tamil Nadu", "type": "Tricontinental Cape (Indian Ocean Confluence)", "region": "Indian Ocean Cape"},
    "colachel": {"lat": 8.1750, "lon": 77.2550, "state": "Tamil Nadu", "type": "Deep Sea Longliner Harbor", "region": "South Arabian Sea / Cape"},

    # Puducherry
    "puducherry": {"lat": 11.9416, "lon": 79.8083, "state": "Puducherry", "type": "Fishing Harbor & Port", "region": "Central Bay of Bengal (Coromandel Coast)"},
    "pondicherry": {"lat": 11.9416, "lon": 79.8083, "state": "Puducherry", "type": "Fishing Harbor & Port", "region": "Central Bay of Bengal (Coromandel Coast)"},

    # Andhra Pradesh
    "visakhapatnam": {"lat": 17.6868, "lon": 83.2185, "state": "Andhra Pradesh", "type": "Major Port & Fishing Harbor", "region": "Central Bay of Bengal (Andhra Coast)"},
    "vizag": {"lat": 17.6868, "lon": 83.2185, "state": "Andhra Pradesh", "type": "Major Fishing Harbor", "region": "Central Bay of Bengal (Andhra Coast)"},
    "kakinada": {"lat": 16.9891, "lon": 82.2475, "state": "Andhra Pradesh", "type": "Deep Water Port & Fishing Harbor", "region": "Central Bay of Bengal (Andhra Coast)"},
    "machilipatnam": {"lat": 16.1875, "lon": 81.1389, "state": "Andhra Pradesh", "type": "Gilakaladindi Fishing Harbor", "region": "Central Bay of Bengal (Andhra Coast)"},
    "nizampatnam": {"lat": 15.9060, "lon": 80.6720, "state": "Andhra Pradesh", "type": "Major Fishing Harbor", "region": "Central Bay of Bengal (Andhra Coast)"},
    "krishnapatnam": {"lat": 14.2500, "lon": 80.1200, "state": "Andhra Pradesh", "type": "Deep Sea Commercial Port", "region": "Central Bay of Bengal (Andhra Coast)"},
    "bhavanapadu": {"lat": 18.5600, "lon": 84.3400, "state": "Andhra Pradesh", "type": "Fishing Harbor", "region": "North Bay of Bengal (Andhra Coast)"},

    # Odisha
    "paradeep": {"lat": 20.3167, "lon": 86.6167, "state": "Odisha", "type": "Major Port & Fishing Harbor", "region": "North Bay of Bengal (Odisha Coast)"},
    "paradip": {"lat": 20.3167, "lon": 86.6167, "state": "Odisha", "type": "Major Port", "region": "North Bay of Bengal (Odisha Coast)"},
    "puri": {"lat": 19.8135, "lon": 85.8312, "state": "Odisha", "type": "Penthakata Fishing Center", "region": "North Bay of Bengal (Odisha Coast)"},
    "dhamra": {"lat": 20.8000, "lon": 86.9500, "state": "Odisha", "type": "Dhamra Port & Fishing Harbor", "region": "North Bay of Bengal (Odisha Coast)"},
    "gopalpur": {"lat": 19.2600, "lon": 84.9100, "state": "Odisha", "type": "Deep Water Port", "region": "North Bay of Bengal (Odisha Coast)"},
    "chandipur": {"lat": 21.4700, "lon": 87.0200, "state": "Odisha", "type": "Intertidal Fishing Center", "region": "North Bay of Bengal (Odisha Coast)"},

    # West Bengal
    "digha": {"lat": 21.6266, "lon": 87.5074, "state": "West Bengal", "type": "Sankarpur / Digha Fishing Harbor", "region": "North Bay of Bengal (Bengal Coast)"},
    "sankarpur": {"lat": 21.6300, "lon": 87.5700, "state": "West Bengal", "type": "Major Trawler Harbor", "region": "North Bay of Bengal (Bengal Coast)"},
    "haldia": {"lat": 22.0667, "lon": 88.0667, "state": "West Bengal", "type": "Riverine Major Port", "region": "North Bay of Bengal (Bengal Coast)"},
    "kolkata": {"lat": 22.5726, "lon": 88.3639, "state": "West Bengal", "type": "Port of Kolkata", "region": "North Bay of Bengal (Bengal Coast)"},
    "kakdwip": {"lat": 21.8700, "lon": 88.1900, "state": "West Bengal", "type": "Sundarbans Gateway Harbor", "region": "North Bay of Bengal (Sundarbans)"},
    "namkhana": {"lat": 21.7600, "lon": 88.2300, "state": "West Bengal", "type": "Sundarbans Marine Center", "region": "North Bay of Bengal (Sundarbans)"},
    "frazerganj": {"lat": 21.5800, "lon": 88.2500, "state": "West Bengal", "type": "Deep Sea Trawler Harbor", "region": "North Bay of Bengal (Sundarbans)"},

    # Andaman & Nicobar / Lakshadweep
    "port blair": {"lat": 11.6234, "lon": 92.7265, "state": "Andaman & Nicobar", "type": "Junglighat Fishing Harbor", "region": "Andaman & Nicobar Marine Basin"},
    "kavaratti": {"lat": 10.5667, "lon": 72.6333, "state": "Lakshadweep", "type": "Tuna Pole-and-Line Center", "region": "Lakshadweep Archipelago"},
    "agatti": {"lat": 10.8500, "lon": 72.1833, "state": "Lakshadweep", "type": "Tuna Fishing Lagoon", "region": "Lakshadweep Archipelago"}
}


class CoastalGeocodingEngine:
    """
    Resolves natural language location queries into precise coastal coordinates.
    """

    @classmethod
    def resolve_location(cls, query_text: str) -> Optional[Dict[str, Any]]:
        """
        Extracts known coastal port or town from text query.
        """
        clean_text = (query_text or "").lower()

        # 1. Exact or Substring match in predefined Indian Coastal locations
        for loc_name, data in INDIAN_COASTAL_LOCATIONS.items():
            is_ascii = loc_name.isascii()
            if is_ascii:
                matched = bool(re.search(rf"\b{re.escape(loc_name)}\b", clean_text))
            else:
                matched = loc_name in clean_text
            if matched:
                return {
                    "name": data.get("canonical_name", loc_name.title()),
                    "latitude": data["lat"],
                    "longitude": data["lon"],
                    "state": data["state"],
                    "type": data["type"],
                    "region": data["region"],
                    "matched_by": "indian_coastal_ports_database"
                }

        return None

    @classmethod
    async def geocode_query(cls, location_name: str) -> Optional[Dict[str, Any]]:
        """
        Resolves location name via built-in database first, then Nominatim live geocoder.
        """
        if not location_name:
            return None

        # Try offline database first
        offline_match = cls.resolve_location(location_name)
        if offline_match:
            return offline_match

        # Try Nominatim live geocoding (restricted to India)
        if httpx is not None:
            try:
                headers = {"User-Agent": "Oceanova-Marine-Intelligence/1.0"}
                params = {
                    "q": f"{location_name}, India",
                    "format": "json",
                    "limit": 1
                }
                async with httpx.AsyncClient(timeout=1.0) as client:
                    resp = await client.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers)
                    if resp.status_code == 200:
                        results = resp.json()
                        if results:
                            item = results[0]
                            lat = float(item["lat"])
                            lon = float(item["lon"])
                            # Ensure coordinates are in Indian coastal bounding box
                            if 5.0 <= lat <= 26.0 and 65.0 <= lon <= 95.0:
                                return {
                                    "name": item.get("display_name", location_name),
                                    "latitude": round(lat, 4),
                                    "longitude": round(lon, 4),
                                    "state": "India",
                                    "type": "Nominatim Resolved Landmark",
                                    "region": "Indian Coastal Zone",
                                    "matched_by": "nominatim_live_osm"
                                }
            except Exception:
                pass

        return None


geocoder = CoastalGeocodingEngine()
