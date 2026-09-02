import os
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

from speech_engine import SpeechEngine

app = FastAPI(
    title="Online Speech Microservice",
    description="Backend service integrating Sarvam Saaras v3 STT and Edge-TTS.",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = SpeechEngine()

class TTSRequest(BaseModel):
    text: str
    language_code: str = "ta-IN"
    speaker: Optional[str] = "shubh"

@app.post("/api/speech/stt")
async def speech_to_text(file: UploadFile = File(...)):
    """
    Receives an audio file upload, sends it to Sarvam AI STT (Saaras:v3),
    and returns detected language, native transcript, and translated English text.
    """
    try:
        contents = await file.read()
        filename = file.filename or "speech.wav"
        result = await engine.transcribe_and_translate(contents, filename=filename)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/speech/tts")
async def text_to_speech(request: TTSRequest):
    """
    Accepts JSON with text and target language code, calls Edge-TTS,
    and returns base64 encoded audio.
    """
    try:
        result = await engine.generate_speech(
            text=request.text,
            target_language=request.language_code,
            speaker=request.speaker or "shubh"
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error_detail", "TTS Error"))
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Sarvam AI Speech Microservice running. Upload index.html to static/."}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
