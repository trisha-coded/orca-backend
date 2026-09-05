# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Primary Users (At Sea)**: Coastal fishers and fishing vessel masters/skippers across Indian maritime states (Tamil Nadu, Kerala, Karnataka, Gujarat, Andhra Pradesh, Maharashtra, Odisha, West Bengal) operating artisanal motorized craft, traditional canoes, mechanized trawlers, and deep-sea vessels. Operating under outdoor maritime glare, heavy vessel pitch/roll, and high-stress sea conditions; requiring instant go/no-go clarity, voice-first interaction, and vernacular mother-tongue advisories.
- **Secondary Users (Shore-Side)**: Harbor dispatchers, fisheries cooperative managers, coastal community safety monitors, and maritime port authorities tracking fleet movements, weather depressions, tidal safety windows, and international boundary buffer compliance.

## Product Purpose

Project Oceanova (Maritime Agentic Reasoning, Location Intelligence, and Nautical Decision Platform) / ORCA is an autonomous multi-agent marine intelligence platform built to eliminate maritime tragedies and optimize fishing livelihoods. It synthesizes real-time marine meteorology, satellite oceanographic biological productivity (PFZ), spatial maritime boundary geofencing, harmonic tidal phases, and safest route calculations into plain-language actionable decisions and VHF broadcast scripts.

## Positioning

Unlike disconnected single-source tools (generic weather forecasts or static INCOIS PDF charts), Oceanova couples real-time Copernicus SST and GlobColour chlorophyll fronts with deterministic geodesic geofencing (EEZ v12 / IMBL) within a multi-agent LangGraph orchestrator. It delivers holistic, contextualized decision-support that informs skippers of optimal fishing grounds while providing immediate, transparent boundary and storm buffer telemetry.

## Operating Context

- **Maritime Field Environment**: Direct sunlight and ocean glare, wet touchscreen interfaces, noisy marine engines, and intermittent cellular/satellite data. Demands hands-free voice query input, high-contrast dark mission-control displays, large tactile targets, and VHF-ready synthesized radio scripts.
- **Harbor & Fleet Operations**: Desktop and tablet dispatch consoles used by fisheries cooperative managers and dispatch officers to plan voyage departure windows around astronomical tidal cycles and monitor collective fleet proximity to foreign boundary buffer zones.

## Capabilities and Constraints

- **Autonomous Agentic Decision Pipeline**: FastAPI backend driving LangGraph conditional domain agents (Conversational NLU Supervisor, Marine Weather Agent, Oceanographic PFZ Agent, Geofence/IMBL Boundary Agent, Harmonic Tides Agent, and Routing Agent).
- **Decision-Support Philosophy**: Advisory decision-support that highlights optimal potential fishing zones (PFZ) alongside prominent proximity warnings and risk indices, ensuring the skipper retains ultimate operational authority while fully informed of risks.
- **Deterministic Spatial & Environmental Gates**: Sub-second geodesic proximity evaluation to the Sri Lanka IMBL and Pakistan IMBL, Marine Protected Area (MPA) boundaries, wave height thresholds, and cyclonic depression risk scores.
- **Multilingual Vernacular Synthesis**: Real-time NLU and advisory generation in English, Tamil (`ta`), Hindi (`hi`), Malayalam (`ml`), and Telugu (`te`).
- **Harmonic Tidal Engine**: Astronomical constituent tidal calculations providing high/low tide predictions and harbor draft safety windows.

## Brand Commitments

- **Name**: Project Oceanova — Agentic Marine Intelligence Platform (developed for Smart India Hackathon 2026).
- **Aesthetic**: Deep dark oceanic mission-control HUD with maritime brass/amber instrument accents, crisp bioluminescent cyan telemetry, and scientific precision typography.
- **Voice**: Authoritative, calm, direct, and protective; speaking as an experienced nautical tactical navigator rather than an abstract chatbot.

## Evidence on Hand

- `app/main.py`: Operational FastAPI backend with `/api/v1/advisory`, `/api/v1/health`, direct module check endpoints, and Swagger/ReDoc documentation.
- `app/graph.py` & `app/agents/`: Multi-agent LangGraph pipeline with specialized domain agents.
- `frontend/`: Production-ready unified base template, design token architecture (`css/tokens.css`), mission-control components (`css/components.css`), base layout (`css/base.css`), and interactive GSAP/Three.js depth visualizer (`js/app.js`).
- `india_neighbors_eez (1).geojson`: Verified geospatial boundaries for Indian EEZ and neighboring maritime zones.

## Product Principles

1. **Unequivocal Go/No-Go Clarity**: Every satellite raster, weather model, and geodesic calculation must resolve into a clear, immediately actionable verdict in the fisher's native language.
2. **Transparent Advisory Support**: Never hide or suppress critical data without explanation. Present optimal fishing grounds alongside clear, prominent proximity warnings so the master can evaluate risk with total operational clarity.
3. **Low-Cognitive-Load Field Legibility**: High contrast, clean visual hierarchy, and information density without visual clutter; engineered specifically for readability under direct nautical sunlight and maritime glare.
4. **Explainable Agent Reasoning**: Maintain transparent multi-agent reasoning traces, latency metrics, and deterministic rule citations to cultivate trust across both sea skippers and shore authorities.

## Accessibility & Inclusion

- Multilingual voice synthesis and VHF-ready radio scripts to serve artisanal fishers with varying degrees of text literacy.
- High-contrast visual tokens complying with WCAG AA standards against dark abyssal surfaces.
- Fully accessible keyboard navigation and unambiguous focus indicators across all controls.
