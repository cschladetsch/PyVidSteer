from __future__ import annotations
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .backends import create_backend
from .config import load_config
from .generation import GenerationEngine
from .guardrails import GuardrailLayer
from .models import PromptRequest, SessionStateResponse
from .session import SessionManager

_config = load_config()
_segments_dir = Path(_config.segments_dir)
_segments_dir.mkdir(parents=True, exist_ok=True)

_primary = create_backend(_config.backend.primary, _segments_dir)
_fallbacks = [create_backend(name, _segments_dir) for name in _config.backend.fallback]
_engine = GenerationEngine(_primary, _fallbacks, _config)
_guardrail = GuardrailLayer(profile=_config.guardrails.profile)
_manager = SessionManager(_engine, _guardrail, _config)


@asynccontextmanager
async def lifespan(app: FastAPI):
    default_session_id = _manager.create_session()
    app.state.default_session_id = default_session_id
    yield


app = FastAPI(title="InteractiveGen", version="0.1.0", lifespan=lifespan)
app.mount("/segments", StaticFiles(directory=str(_segments_dir)), name="segments")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse("static/index.html")


@app.get("/default-session")
async def default_session():
    return {"session_id": app.state.default_session_id}


@app.post("/sessions")
async def create_session():
    session_id = _manager.create_session()
    return {"session_id": session_id}


@app.get("/sessions/{session_id}", response_model=SessionStateResponse)
async def get_session(session_id: str):
    try:
        session = _manager.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    segment_url = None
    if session.current_segment:
        segment_url = f"/segments/{session.current_segment.name}"

    return SessionStateResponse(
        session_id=session.session_id,
        playback_state=session.state,
        current_segment_url=segment_url,
        context_summary=session.context,
    )


@app.post("/sessions/{session_id}/prompt")
async def submit_prompt(session_id: str, body: PromptRequest):
    try:
        return await _manager.submit_prompt(session_id, body.text)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@app.get("/sessions/{session_id}/events")
async def session_events(session_id: str):
    """Server-Sent Events stream -- pushes segment URLs and state changes to the client."""
    try:
        _manager.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    async def stream():
        async for event in _manager.subscribe(session_id):
            yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(0)

    return StreamingResponse(stream(), media_type="text/event-stream")
