from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class PlaybackState(str, Enum):
    IDLE_LOOP = "IDLE_LOOP"
    GENERATING_TARGET = "GENERATING_TARGET"
    GENERATING_TRANSITION = "GENERATING_TRANSITION"
    PLAYING_TRANSITION = "PLAYING_TRANSITION"


class GuardrailVerdict(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class PromptRequest(BaseModel):
    text: str


class PromptResponse(BaseModel):
    status: GuardrailVerdict
    reason: Optional[str] = None


class SessionStateResponse(BaseModel):
    session_id: str
    playback_state: PlaybackState
    current_segment_url: Optional[str] = None
    context_summary: str = ""
