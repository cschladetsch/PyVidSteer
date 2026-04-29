from __future__ import annotations
import asyncio
import base64
import os
from pathlib import Path

import httpx

from .base import VideoBackend, GeneratedSegment


class RunwayBackend(VideoBackend):
    """
    Runway Gen-3 Alpha API.
    Required env vars:
      RUNWAY_API_KEY   -- API key
      RUNWAY_BASE_URL  -- override default endpoint (optional)
    """

    _API_VERSION = "2024-11-06"

    def __init__(self, segments_dir: Path = Path("segments")):
        self._api_key = os.environ["RUNWAY_API_KEY"]
        self._base_url = os.environ.get("RUNWAY_BASE_URL", "https://api.dev.runwayml.com")
        self._dir = segments_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "X-Runway-Version": self._API_VERSION,
        }

    async def generate_from_prompt(self, prompt: str, duration_seconds: int) -> GeneratedSegment:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{self._base_url}/v1/image_to_video",
                headers=self._headers(),
                json={
                    "model": "gen3a_turbo",
                    "promptText": prompt,
                    "duration": min(duration_seconds, 10),
                    "ratio": "1280:768",
                },
            )
            resp.raise_for_status()
            task_id = resp.json()["id"]
            return await self._poll_and_download(client, task_id, f"runway_{task_id}.mp4")

    async def generate_transition(
        self, frame_a: Path, frame_b: Path, max_duration_seconds: int
    ) -> GeneratedSegment:
        img_b64 = base64.b64encode(frame_a.read_bytes()).decode()
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{self._base_url}/v1/image_to_video",
                headers=self._headers(),
                json={
                    "model": "gen3a_turbo",
                    "promptImage": f"data:image/jpeg;base64,{img_b64}",
                    "promptText": "smooth transition maintaining scene continuity and consistent style",
                    "duration": min(max_duration_seconds, 5),
                },
            )
            resp.raise_for_status()
            task_id = resp.json()["id"]
            return await self._poll_and_download(client, task_id, f"runway_transition_{task_id}.mp4")

    async def _poll_and_download(
        self, client: httpx.AsyncClient, task_id: str, filename: str
    ) -> GeneratedSegment:
        dest = self._dir / filename
        while True:
            await asyncio.sleep(5)
            resp = await client.get(
                f"{self._base_url}/v1/tasks/{task_id}", headers=self._headers()
            )
            resp.raise_for_status()
            data = resp.json()
            status = data["status"]
            if status == "SUCCEEDED":
                video_url = data["output"][0]
                download = await client.get(video_url)
                dest.write_bytes(download.content)
                return GeneratedSegment(path=dest, duration_seconds=float(data.get("duration", 6)))
            if status in ("FAILED", "CANCELLED"):
                raise RuntimeError(f"Runway generation failed: {data.get('failure', status)}")
