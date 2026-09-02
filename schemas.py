from pydantic import BaseModel
from typing import Optional

class TranslationRequest(BaseModel):
    source_text: str
    source_language: str
    target_language: str

class TranslationResponse(BaseModel):
    translated_text: str
    source_language: str
    target_language: str

class TTSRequest(BaseModel):
    text: str
    language: str
    gender: str = "female"

class TTSResponse(BaseModel):
    audio_base64: str
    language: str
    gender: str

# For STT, we typically receive audio files, so request might be handled via Form/File in FastAPI.
# But we can define a response schema.
class STTResponse(BaseModel):
    transcript: str
    detected_language: str
