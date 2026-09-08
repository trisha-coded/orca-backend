🌊 OCEANOVA

Conversational AI for marine safety and fishing advisory — one question, one synthesized answer.

Smart India Hackathon 2026 · Problem Statement ID 26176 · ORCA — Marine Ecosystem Reasoning with Collaborative Agents · Theme: Disaster Management · Team SIH 182

The Problem

Marine data — weather, tides, potential fishing zones, maritime boundaries, hazard alerts — already exists, but it's scattered across five different technical sources and too fragmented for on-ground use. A fisherman heading out at 4 AM doesn't have time to cross-check all of them. Delays and wrong calls cost lives, fuel, and catch.

What OCEANOVA Does

OCEANOVA is a multi-agent conversational AI that answers marine queries directly — "Is it safe to fish tomorrow?" — by voice or text, in the user's own language, and returns one synthesized, evidence-backed answer instead of five raw dashboards.

🎙️ Voice-first, multilingual — built for users who won't type or read a dashboard
🧭 Radar + advisory fused — live collision-avoidance sits in the same interface as marine advisory
🔍 Explainable by design — every recommendation shows its reasoning (e.g. "89%: SST + upwelling front match")
🗺️ Geofencing as reasoning, not a map layer — IMBL/MPA proximity directly shapes every safety and routing decision
🛟 Fails gracefully — GPS or live-feed loss falls back to manual harbour selection or clearly-flagged cached data, never a silent failure
How It Works
User Query (voice/text)
        │
        ▼
Supervisor Agent  →  parses intent, resolves location, detects language
        │
        ▼
Multi-Source Retrieval  →  live weather, ocean conditions, static EEZ/MPA boundaries (parallel fetch)
        │
        ▼
Parallel Agent Reasoning
   ┌─────────┬─────────┬──────────┬────────┬──────────┐
   │ Weather │  Ocean   │ Geofence │  Tides │  Routing │   (concurrent)
   └─────────┴─────────┴──────────┴────────┴──────────┘
        │
        ▼
Synthesizer Agent  →  merges outputs, applies deterministic safety overrides,
                       generates plain-language advisory + VHF broadcast script
        │
        ▼
Multilingual Output  →  text · regional voice audio (Indic TTS) · GeoJSON map layer

Responses are spatially cached in Redis for 15 minutes for fast repeat lookups in high-traffic coastal zones — hazard alerts (cyclone, lightning) always bypass the cache and fetch live.

Tech Stack
Layer	Technology
Backend	FastAPI (async, parallel agent orchestration)
Agent framework	LangGraph / CrewAI
Marine data	Open-Meteo Marine API (wave, wind, SST)
Geospatial	PostGIS, GeoPandas, Xarray, Rasterio, Shapely
Geofencing	Ray-casting algorithm on EEZ/MPA boundary data — fully offline
Tides	Harmonic tide engine — fully offline
Caching	Redis
Inference	Gemini
Speech	Bhashini API, OpenAI Whisper (STT) · Edge-TTS, Indic-TTS (TTS)
Frontend	React / Next.js (or Flutter), Mapbox GL JS / Leaflet, Tailwind CSS, WebSocket
Deployment	Docker
Project Structure
oceanova/
├── backend/
│   ├── agents/          # Weather, Ocean, Geofence, Tides, Routing agents
│   ├── supervisor/       # Intent parsing, routing logic
│   ├── synthesizer/      # Safety-gated synthesis, advisory generation
│   ├── data/              # Static EEZ/MPA boundary datasets, tide constants
│   └── main.py            # FastAPI entrypoint
├── frontend/
│   ├── components/       # Chat UI, voice widget, map layers
│   └── App.tsx
├── docs/                  # Architecture notes, pitch materials
└── README.md

(Adjust to match your actual repo layout — this reflects the architecture described in the SIH submission.)

Getting Started
Prerequisites
Python 3.10+
Node.js 18+
Redis (local or hosted)
API keys: Gemini, Bhashini (optional for regional TTS/STT)
Backend
bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add GEMINI_API_KEY, REDIS_URL, etc.
uvicorn main:app --reload
Frontend
bash
cd frontend
npm install
npm run dev
Environment Variables
Variable	Description
GEMINI_API_KEY	Inference for intent parsing & synthesis
REDIS_URL	Cache + fallback store
BHASHINI_API_KEY	Regional STT/TTS (optional)
OPEN_METEO_BASE_URL	Marine weather data source
Team
Role	Focus
Agentic AI & LLM Engineer	Multi-agent graph, prompt engineering, synthesis pipeline
Geospatial & Data Engineer	Satellite/ocean data pipeline, geofencing, spatial database
Full-Stack / Map Frontend Engineer	Conversational UI, voice widget, interactive map layers
Speech & Multilingual AI Engineer	STT/TTS integration, regional dialect localization
Backend & Systems Integrator	API routing, agent concurrency, caching, deployment
Status

Prototype — orchestrator, parallel agents, and core UI are built and running. Offline-capable tide engine and geofencing ship today; live VHF integration, field validation, and load testing are on the roadmap.

References

Full research and policy references (INCOIS, CMFRI, NCAER, PMMSY, and cited papers) are listed in the project's SIH submission deck.
