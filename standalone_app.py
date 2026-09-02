import uvicorn
from fastapi import FastAPI
from router import router as speech_router

app = FastAPI(
    title="Speech & Multilingual Unit MVP (Open Source Edition)",
    description="Microservice for ASR (Whisper), NMT (IndicTrans2), and TTS (Edge-TTS) for the Marine Agentic AI Platform.",
    version="0.2.0"
)

app.include_router(speech_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("standalone_app:app", host="0.0.0.0", port=8000, reload=True)
