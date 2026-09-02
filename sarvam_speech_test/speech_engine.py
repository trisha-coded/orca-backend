import asyncio
import base64
from io import BytesIO

from config import SARVAM_API_KEY

try:
    from sarvamai import SarvamAI
except ImportError:
    SarvamAI = None

try:
    import edge_tts
except ImportError:
    edge_tts = None

try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None


VOICE_MAP = {
    "en": ("en-IN-PrabhatNeural", "en-IN-NeerjaNeural"),
    "ta": ("ta-IN-ValluvarNeural", "ta-IN-PallaviNeural"),
    "te": ("te-IN-MohanNeural", "te-IN-ShrutiNeural"),
    "ml": ("ml-IN-MidhunNeural", "ml-IN-SobhanaNeural"),
    "hi": ("hi-IN-MadhurNeural", "hi-IN-SwaraNeural"),
    "bn": ("bn-IN-BashkarNeural", "bn-IN-TanishaaNeural"),
    "gu": ("gu-IN-NiranjanNeural", "gu-IN-DhwaniNeural"),
    "kn": ("kn-IN-GaganNeural", "kn-IN-SapnaNeural"),
    "mr": ("mr-IN-ManoharNeural", "mr-IN-AarohiNeural"),
    "od": ("hi-IN-MadhurNeural", "hi-IN-SwaraNeural"),
}

TRANSLATOR_LANGUAGE = {
    "ta": "tamil", "te": "telugu", "ml": "malayalam", "hi": "hindi",
    "bn": "bengali", "gu": "gujarati", "kn": "kannada", "mr": "marathi",
    "od": "odia (oriya)",
}


class SpeechEngine:
    """Sarvam Saaras v3 STT with Edge-TTS synthesis."""

    def __init__(self):
        self.client = SarvamAI(api_subscription_key=SARVAM_API_KEY) if SarvamAI and SARVAM_API_KEY else None

    def _require_client(self):
        if not SARVAM_API_KEY:
            raise RuntimeError("SARVAM_API_KEY is not configured.")
        if not self.client:
            raise RuntimeError("Sarvam SDK is unavailable. Install the project requirements.")
        return self.client

    @staticmethod
    def _audio_file(audio_bytes: bytes, filename: str) -> BytesIO:
        audio_file = BytesIO(audio_bytes)
        audio_file.name = filename or "speech.webm"
        return audio_file

    async def transcribe_and_translate(self, audio_bytes: bytes, filename: str = "speech.webm") -> dict:
        """Detect and transcribe Indian-language audio, then translate it to English."""
        return await asyncio.to_thread(self._transcribe_and_translate, audio_bytes, filename)

    def _transcribe_and_translate(self, audio_bytes: bytes, filename: str) -> dict:
        client = self._require_client()
        native = client.speech_to_text.transcribe(
            file=self._audio_file(audio_bytes, filename),
            model="saaras:v3",
            language_code="unknown",
            mode="transcribe",
        )
        translated = client.speech_to_text.transcribe(
            file=self._audio_file(audio_bytes, filename),
            model="saaras:v3",
            language_code="unknown",
            mode="translate",
        )
        return {
            "status": "success",
            "native_transcript": native.transcript,
            "english_transcript": translated.transcript,
            "detected_language": getattr(native, "language_code", "unknown"),
            "backend": "Sarvam Saaras v3",
        }

    async def generate_speech(self, text: str, target_language: str = "ta-IN", speaker: str = "shubh") -> dict:
        """Translate when necessary and generate MP3 speech with Edge-TTS."""
        if not text.strip():
            raise ValueError("Text must not be empty.")
        if not edge_tts:
            raise RuntimeError("Edge-TTS is unavailable. Install the project requirements.")

        language_prefix = target_language.split("-", 1)[0].lower()
        male_voice, female_voice = VOICE_MAP.get(language_prefix, VOICE_MAP["en"])
        voice = male_voice if speaker == "shubh" else female_voice
        translated_text = text

        translator_language = TRANSLATOR_LANGUAGE.get(language_prefix)
        if translator_language and GoogleTranslator:
            try:
                translated_text = await asyncio.to_thread(
                    GoogleTranslator(source="en", target=translator_language).translate, text
                ) or text
            except Exception:
                translated_text = text

        audio_data = b""
        communicate = edge_tts.Communicate(translated_text, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        audio_base64 = base64.b64encode(audio_data).decode("utf-8")
        if not audio_base64:
            raise RuntimeError("Edge-TTS returned no audio.")

        return {
            "status": "success",
            "audio_base64": audio_base64,
            "audio_mime_type": "audio/mpeg",
            "text": text,
            "translated_text": translated_text,
            "voice": voice,
            "language": target_language,
            "backend": "Edge-TTS",
        }
