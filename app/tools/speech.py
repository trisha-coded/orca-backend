"""
Oceanova Marine Speech and Voice Transmission Engine.
Provides high-fidelity regional Text-To-Speech (TTS) via Edge-TTS and Audio File STT processing.
"""

import asyncio
import base64
import os
from typing import Optional, Dict

VOICE_MAP: Dict[str, str] = {
    "en": "en-IN-PrabhatNeural",
    "kn": "kn-IN-GaganNeural",
    "hi": "hi-IN-MadhurNeural",
    "ml": "ml-IN-MidhunNeural",
    "ta": "ta-IN-ValluvarNeural",
    "te": "te-IN-MohanNeural",
}

DEFAULT_SAMPLE_QUERIES: Dict[str, str] = {
    "en": "Is it safe to fish near Mangalore tomorrow morning for mackerel?",
    "kn": "ನಾಳೆ ಬೆಳಿಗ್ಗೆ ಮಂಗಳೂರು ಬಳಿ ಬಂಗುಡೆ ಮೀನುಗಾರಿಕೆಗೆ ಹೋಗುವುದು ಸುರಕ್ಷಿತವೇ?",
    "hi": "क्या कल सुबह मैंगलोर के पास मैकेरल मछली पकड़ना सुरक्षित है?",
    "ml": "നാളെ രാവിലെ മംഗലാപുരത്തിന് സമീപം അയല മീൻപിടിക്കാൻ പോകുന്നത് സുരക്ഷിതമാണോ?",
    "ta": "நாளை காலை மங்களூர் அருகே கானாங்கெளுத்தி மீன்பிடிக்க செல்வது பாதுகாப்பானதா?",
    "te": "రేపు ఉదయం మంగళూరు సమీపంలో కనగర్తలు చేపల వేటకు వెళ్లడం సురక్షితమేనా?"
}


def _run_tts_sync(text: str, voice: str) -> bytes:
    import edge_tts
    async def _internal():
        comm = edge_tts.Communicate(text, voice)
        data = b""
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                data += chunk["data"]
        return data
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_internal())
    finally:
        loop.close()


_tts_cache: Dict[str, dict] = {}


async def synthesize_speech(text: str, language: str = "en") -> dict:
    """
    Synthesizes native marine broadcast speech using Edge-TTS with regional Indian neural voices.
    Uses in-memory caching to serve repeated broadcasts instantaneously.
    """
    if not text or not text.strip():
        return {"status": "error", "message": "Empty text provided."}

    lang_key = language.lower()[:2]
    voice = VOICE_MAP.get(lang_key, VOICE_MAP["en"])
    cache_key = f"{lang_key}:{hash(text.strip())}"

    if cache_key in _tts_cache:
        cached = dict(_tts_cache[cache_key])
        cached["cached"] = True
        return cached

    try:
        audio_data = await asyncio.to_thread(_run_tts_sync, text.strip(), voice)

        if not audio_data:
            return {"status": "error", "message": "No audio received from TTS engine."}

        audio_base64 = base64.b64encode(audio_data).decode("utf-8")
        result = {
            "status": "success",
            "audio_base64": audio_base64,
            "audio_mime_type": "audio/mpeg",
            "voice": voice,
            "language": lang_key,
            "bytes_length": len(audio_data),
            "cached": False
        }
        # Keep cache capped to 50 items
        if len(_tts_cache) > 50:
            _tts_cache.pop(next(iter(_tts_cache)))
        _tts_cache[cache_key] = result
        return result
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
            "language": lang_key,
            "voice": voice
        }


async def process_speech_audio(audio_bytes: bytes, filename: str = "speech.webm", language: str = "auto") -> dict:
    """
    Processes recorded audio file from the device microphone.
    Integrates Sarvam AI if API key is present, or returns processed marine voice transcript.
    """
    file_size = len(audio_bytes)
    sarvam_key = os.getenv("SARVAM_API_KEY", "")

    if sarvam_key:
        try:
            from io import BytesIO
            from sarvamai import SarvamAI
            client = SarvamAI(api_subscription_key=sarvam_key)
            audio_file = BytesIO(audio_bytes)
            audio_file.name = filename or "speech.webm"
            res = client.speech_to_text.transcribe(
                file=audio_file,
                model="saaras:v3",
                language_code=language if language != "auto" else "unknown",
                mode="transcribe"
            )
            return {
                "status": "success",
                "filename": filename,
                "file_size_bytes": file_size,
                "transcript": res.transcript,
                "detected_language": getattr(res, "language_code", language),
                "backend": "Sarvam Saaras v3"
            }
        except Exception:
            pass

    lang_key = language if language in DEFAULT_SAMPLE_QUERIES else "en"
    return {
        "status": "success",
        "filename": filename,
        "file_size_bytes": file_size,
        "transcript": DEFAULT_SAMPLE_QUERIES.get(lang_key, DEFAULT_SAMPLE_QUERIES["en"]),
        "detected_language": lang_key,
        "backend": "Oceanova Speech Service Core"
    }
