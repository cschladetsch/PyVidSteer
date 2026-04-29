from __future__ import annotations
import asyncio
import subprocess
from pathlib import Path

from .base import VideoBackend, GeneratedSegment


class MockBackend(VideoBackend):
    """
    Generates solid-colour test videos via ffmpeg.
    No API credentials required -- useful for end-to-end testing.
    """

    def __init__(self, segments_dir: Path = Path("segments")):
        self._dir = segments_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    async def generate_from_prompt(self, prompt: str, duration_seconds: int) -> GeneratedSegment:
        await asyncio.sleep(1.5)  # simulate API round-trip latency
        slug = abs(hash(prompt)) % 100_000
        path = self._dir / f"target_{slug:05d}.mp4"
        if not path.exists():
            await asyncio.to_thread(_make_colour_video, path, duration_seconds, "#3a6186")
        return GeneratedSegment(path=path, duration_seconds=float(duration_seconds))

    async def generate_transition(
        self, frame_a: Path, frame_b: Path, max_duration_seconds: int
    ) -> GeneratedSegment:
        await asyncio.sleep(0.8)
        path = self._dir / "mock_transition.mp4"
        if not path.exists():
            await asyncio.to_thread(_make_colour_video, path, 2, "#89216b")
        return GeneratedSegment(path=path, duration_seconds=2.0)


def _make_colour_video(path: Path, duration: int, color: str) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c={color}:s=640x360:d={duration}",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
