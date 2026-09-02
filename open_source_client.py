import os
import io
import base64
import asyncio
from config import settings
from schemas import TranslationRequest, TranslationResponse, TTSRequest, TTSResponse, STTResponse

# Try to import heavy dependencies, handle graceful failure if not installed yet
try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

try:
    import edge_tts
except ImportError:
    edge_tts = None

try:
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
except ImportError:
    torch = None
    AutoModelForSeq2SeqLM = None

class OpenSourceAIClient:
    def __init__(self):
        self.whisper_model_size = settings.whisper_model_size
        self._whisper_model = None
        self._indic2en_model = None
        self._indic2en_tokenizer = None
        self._en2indic_model = None
        self._en2indic_tokenizer = None
        
        # Lazy loading flag
        self.models_loaded = False

    def load_models(self):
        if self.models_loaded:
            return
            
        print("Loading open source models... This may take a while and requires significant memory.")
        
        # Load Faster Whisper
        if WhisperModel:
            print(f"Loading Whisper model ({self.whisper_model_size})...")
            # Using cpu by default for MVP, can be changed to 'cuda'
            self._whisper_model = WhisperModel(self.whisper_model_size, device="cpu", compute_type="int8")
        
        # Load IndicTrans2
        if AutoModelForSeq2SeqLM and torch:
            # We use the smaller models or standard models depending on memory
            # For this MVP we'll configure the standard ai4bharat models
            
            print("Loading IndicTrans2 (Indic to English)...")
            indic2en_id = "ai4bharat/indictrans2-indic-en-1B"
            try:
                self._indic2en_tokenizer = AutoTokenizer.from_pretrained(indic2en_id, trust_remote_code=True)
                self._indic2en_model = AutoModelForSeq2SeqLM.from_pretrained(indic2en_id, trust_remote_code=True)
            except Exception as e:
                print(f"Failed to load IndicTrans2 (Indic-En): {e}")

            print("Loading IndicTrans2 (English to Indic)...")
            en2indic_id = "ai4bharat/indictrans2-en-indic-1B"
            try:
                self._en2indic_tokenizer = AutoTokenizer.from_pretrained(en2indic_id, trust_remote_code=True)
                self._en2indic_model = AutoModelForSeq2SeqLM.from_pretrained(en2indic_id, trust_remote_code=True)
            except Exception as e:
                print(f"Failed to load IndicTrans2 (En-Indic): {e}")
                
        self.models_loaded = True

    async def translate(self, request: TranslationRequest) -> TranslationResponse:
        self.load_models()
        
        if not self._indic2en_model or not self._en2indic_model:
            return TranslationResponse(
                translated_text="Error: Transformers or IndicTrans2 models not loaded properly.",
                source_language=request.source_language,
                target_language=request.target_language
            )

        try:
            # Simple heuristic: if target is english, use indic2en
            # If source is english, use en2indic
            if request.target_language.startswith("en"):
                tokenizer = self._indic2en_tokenizer
                model = self._indic2en_model
            else:
                tokenizer = self._en2indic_tokenizer
                model = self._en2indic_model

            # IndicTrans2 expects specific formatting, simplified for MVP
            inputs = tokenizer(request.source_text, return_tensors="pt")
            outputs = model.generate(**inputs, max_length=256)
            translated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)

            return TranslationResponse(
                translated_text=translated_text,
                source_language=request.source_language,
                target_language=request.target_language
            )
        except Exception as e:
            return TranslationResponse(
                translated_text=f"Translation Error: {str(e)}",
                source_language=request.source_language,
                target_language=request.target_language
            )

    async def tts(self, request: TTSRequest) -> TTSResponse:
        if not edge_tts:
            return TTSResponse(audio_base64="Error: edge-tts not installed", language=request.language, gender=request.gender)

        try:
            # Basic mapping. Edge-TTS requires specific voice tags.
            # E.g., hi-IN-SwaraNeural (Female), hi-IN-MadhurNeural (Male)
            # ta-IN-PallaviNeural (Tamil Female), etc.
            
            # Simple mapping fallback for MVP
            voice = settings.edge_tts_voice_default
            if "hi" in request.language.lower():
                voice = "hi-IN-SwaraNeural" if request.gender == "female" else "hi-IN-MadhurNeural"
            elif "ta" in request.language.lower():
                voice = "ta-IN-PallaviNeural" if request.gender == "female" else "ta-IN-ValluvarNeural"
            elif "te" in request.language.lower():
                voice = "te-IN-ShrutiNeural" if request.gender == "female" else "te-IN-MohanNeural"

            communicate = edge_tts.Communicate(request.text, voice)
            
            # edge-tts generates audio asynchronously
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            
            audio_base64 = base64.b64encode(audio_data).decode("utf-8")
            
            return TTSResponse(
                audio_base64=audio_base64,
                language=request.language,
                gender=request.gender
            )
        except Exception as e:
            return TTSResponse(
                audio_base64=f"Error: {str(e)}",
                language=request.language,
                gender=request.gender
            )

    async def stt(self, audio_bytes: bytes, language: str) -> STTResponse:
        self.load_models()
        
        if not self._whisper_model:
            return STTResponse(transcript="Error: faster-whisper not loaded.", detected_language="")

        try:
            # Faster Whisper needs a file-like object or path
            # We save the bytes temporarily to pass it to whisper
            temp_path = "temp_audio.wav"
            with open(temp_path, "wb") as f:
                f.write(audio_bytes)
                
            segments, info = self._whisper_model.transcribe(temp_path, beam_size=5)
            
            transcript = ""
            for segment in segments:
                transcript += segment.text + " "
                
            os.remove(temp_path)
                
            return STTResponse(
                transcript=transcript.strip(),
                detected_language=info.language
            )
        except Exception as e:
            return STTResponse(
                transcript=f"STT Error: {str(e)}",
                detected_language=language
            )
