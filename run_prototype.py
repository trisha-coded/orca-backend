"""
Project Oceanova / ORCA Marine Intelligence Platform
One-Click Working Prototype Runner

Starts the FastAPI server, serves the modernized Oceanova frontend,
and opens the interactive platform in your default browser.
"""
import sys
import os
import webbrowser
import threading
import time
import uvicorn

from app.config import settings

def open_browser(port):
    time.sleep(1.8)
    url = f"http://127.0.0.1:{port}/"
    print(f"\n🌐 Opening Oceanova Interactive Prototype in your browser: {url}\n")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Browser launch note: {e}")

if __name__ == "__main__":
    port = getattr(settings, "PORT", 8000)
    host = getattr(settings, "HOST", "127.0.0.1")

    print("=" * 74)
    print("🌊  PROJECT OCEANOVA — AGENTIC MARINE INTELLIGENCE PLATFORM")
    print("=" * 74)
    print(f"🚀 Initializing LangGraph Decision Engine & Multi-Agent Pipeline...")
    print(f"🖥️  Interactive Mission Console:  http://127.0.0.1:{port}/")
    print(f"🗺️  Direct Client Link:          http://127.0.0.1:{port}/client")
    print(f"📡  Interactive API Docs:        http://127.0.0.1:{port}/docs")
    print(f"📊  ReDoc Formal Specs:          http://127.0.0.1:{port}/redoc")
    print("=" * 74)
    print("💡 Press Ctrl+C to terminate the server.\n")

    # Launch browser automatically in a background thread
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    # Start Uvicorn ASGI Server
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
