from __future__ import annotations
import asyncio
import subprocess
from pathlib import Path

from .backends.base import VideoBackend, GeneratedSegment
from .config import Config


class GenerationEngine:
    def __init__(self, primary: VideoBackend, fallbacks: list[VideoBackend], config: Config):
        self._primary = primary
        self._fallbacks = fallbacks
        self._config = config
        self._frames_dir = Path("frames")
        self._frames_dir.mkdir(parents=True, exist_ok=True)

    async def generate_target(self, prompt: str, context: str) -> GeneratedSegment:
        enriched = f"{context}\n\n{prompt}".strip() if context else prompt
        return await self._with_fallback(
            lambda b: b.generate_from_prompt(
                enriched, self._config.generation.target_duration_seconds
            )
        )

    async def generate_transition(
        self, current_segment: Path, target_segment: Path
    ) -> GeneratedSegment:
        frame_a = await asyncio.to_thread(self._extract_frame, current_segment, "last")
        frame_b = await asyncio.to_thread(self._extract_frame, target_segment, "first")
        return await self._with_fallback(
            lambda b: b.generate_transition(
                frame_a, frame_b, self._config.generation.transition_max_duration_seconds
            )
        )

    async def _with_fallback(self, operation) -> GeneratedSegment:
        for backend in [self._primary, *self._fallbacks]:
            try:
                return await operation(backend)
            except Exception as exc:
                print(f"[generation] {type(backend).__name__} failed: {exc}")
        raise RuntimeError("All backends failed")

    def _extract_frame(self, video_path: Path, position: str) -> Path:
        out_path = self._frames_dir / f"{video_path.stem}_{position}.jpg"
        if out_path.exists():
            return out_path

        if position == "first":
            timestamp = "00:00:00"
        else:
            duration = _get_video_duration(video_path)
            timestamp = f"{max(0.0, duration - 0.1):.3f}"

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", timestamp,
                "-i", str(video_path),
                "-vframes", "1",
                str(out_path),
            ],
            check=True,
            capture_output=True,
        )
        return out_path


def _get_video_duration(video_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())
