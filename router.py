from fastapi import APIRouter, File, UploadFile, Form, WebSocket
from schemas import TranslationRequest, TranslationResponse, TTSRequest, TTSResponse, STTResponse
from open_source_client import OpenSourceAIClient

router = APIRouter(prefix="/api/v1/speech", tags=["speech"])
client = OpenSourceAIClient()

@router.post("/translate", response_model=TranslationResponse)
async def translate_text(request: TranslationRequest):
    """
    Translates text from a source language to a target language.
    """
    return await client.translate(request)

@router.post("/tts", response_model=TTSResponse)
async def text_to_speech(request: TTSRequest):
    """
    Converts text to speech and returns base64 audio.
    """
    return await client.tts(request)

@router.post("/stt", response_model=STTResponse)
async def speech_to_text(audio: UploadFile = File(...), language: str = Form("hi")):
    """
    Converts audio file to text.
    """
    audio_bytes = await audio.read()
    return await client.stt(audio_bytes, language)

@router.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time audio streaming (Scaffolding).
    """
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # Placeholder for processing real-time audio chunks
            await websocket.send_text(f"Message text was: {data}")
    except Exception as e:
        print(f"WebSocket closed: {e}")
