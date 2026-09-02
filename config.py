from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    whisper_model_size: str = "base"
    # Mapping for edge-tts voices (example mappings, can be expanded)
    # edge-tts provides voices like: hi-IN-SwaraNeural (Female), hi-IN-MadhurNeural (Male)
    edge_tts_voice_default: str = "hi-IN-SwaraNeural"

    class Config:
        env_file = ".env"

settings = Settings()
