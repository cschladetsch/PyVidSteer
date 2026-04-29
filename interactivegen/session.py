from __future__ import annotations
import asyncio
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

from .config import Config
from .generation import GenerationEngine
from .guardrails import GuardrailLayer
from .models import PlaybackState, GuardrailVerdict, PromptResponse


@dataclass
class _Session:
    session_id: str
    state: PlaybackState = PlaybackState.IDLE_LOOP
    current_segment: Path | None = None
    context: str = ""
    prompt_queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=5))
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    task: asyncio.Task | None = None


class SessionManager:
    def __init__(self, engine: GenerationEngine, guardrail: GuardrailLayer, config: Config):
        self._engine = engine
        self._guardrail = guardrail
        self._config = config
        self._sessions: dict[str, _Session] = {}

    def create_session(self, initial_segment: Path | None = None) -> str:
        session_id = str(uuid.uuid4())
        session = _Session(
            session_id=session_id,
            prompt_queue=asyncio.Queue(maxsize=self._config.session.max_queued_prompts),
            current_segment=initial_segment,
        )
        self._sessions[session_id] = session
        session.task = asyncio.create_task(self._run(session))
        return session_id

    def get(self, session_id: str) -> _Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    async def submit_prompt(self, session_id: str, text: str) -> PromptResponse:
        session = self.get(session_id)
        verdict, reason = self._guardrail.classify(text)
        if verdict == GuardrailVerdict.REJECTED:
            return PromptResponse(status=verdict, reason=reason)

        try:
            session.prompt_queue.put_nowait(text)
        except asyncio.QueueFull:
            return PromptResponse(
                status=GuardrailVerdict.REJECTED,
                reason="Prompt queue full -- try again shortly",
            )

        return PromptResponse(status=GuardrailVerdict.APPROVED)

    async def subscribe(self, session_id: str) -> AsyncIterator[dict]:
        session = self.get(session_id)
        queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=32)
        session.subscribers.append(queue)

        # Sync the client with the current segment immediately on connect
        if session.current_segment and session.current_segment.exists():
            yield {"event": "current", "segment_url": f"/segments/{session.current_segment.name}"}

        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            if queue in session.subscribers:
                session.subscribers.remove(queue)

    def _broadcast(self, session: _Session, event: dict) -> None:
        for queue in list(session.subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def _run(self, session: _Session) -> None:
        while True:
            # Wait in IDLE_LOOP state until a prompt arrives
            prompt = await session.prompt_queue.get()

            # --- GENERATING_TARGET ---
            session.state = PlaybackState.GENERATING_TARGET
            self._broadcast(session, {"event": "state", "state": session.state})

            try:
                target = await self._engine.generate_target(prompt, session.context)
            except Exception as exc:
                print(f"[session {session.session_id}] target generation failed: {exc}")
                session.state = PlaybackState.IDLE_LOOP
                self._broadcast(session, {"event": "state", "state": session.state})
                continue

            # --- GENERATING_TRANSITION ---
            session.state = PlaybackState.GENERATING_TRANSITION
            self._broadcast(session, {"event": "state", "state": session.state})

            transition_duration = 0.0
            if session.current_segment and session.current_segment.exists():
                try:
                    transition = await self._engine.generate_transition(
                        session.current_segment, target.path
                    )
                    transition_duration = transition.duration_seconds
                    self._broadcast(session, {
                        "event": "transition",
                        "segment_url": f"/segments/{transition.path.name}",
                    })
                    session.state = PlaybackState.PLAYING_TRANSITION
                    self._broadcast(session, {"event": "state", "state": session.state})
                    # Let the transition play out before switching to the target loop
                    await asyncio.sleep(transition_duration + 0.5)
                except Exception as exc:
                    print(f"[session {session.session_id}] transition generation failed: {exc}")

            # --- Back to IDLE_LOOP with new target ---
            session.current_segment = target.path
            session.context = f"{session.context}\n{prompt}".strip()
            self._broadcast(session, {
                "event": "target",
                "segment_url": f"/segments/{target.path.name}",
            })
            session.state = PlaybackState.IDLE_LOOP
            self._broadcast(session, {"event": "state", "state": session.state})
