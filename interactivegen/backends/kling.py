from __future__ import annotations
import asyncio
import os
from pathlib import Path

import httpx

from .base import VideoBackend, GeneratedSegment


class KlingBackend(VideoBackend):
    """
    Kling video generation API.
    Required env vars:
      KLING_API_KEY   -- API key
      KLING_BASE_URL  -- override default endpoint (optional)
    """

    def __init__(self, segments_dir: Path = Path("segments")):
        self._api_key = os.environ["KLING_API_KEY"]
        self._base_url = os.environ.get("KLING_BASE_URL", "https://api.klingai.com")
        self._dir = segments_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def generate_from_prompt(self, prompt: str, duration_seconds: int) -> GeneratedSegment:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{self._base_url}/v1/videos/text2video",
                headers=self._headers(),
                json={"model": "kling-v1", "prompt": prompt, "duration": duration_seconds},
            )
            resp.raise_for_status()
            task_id = resp.json()["data"]["task_id"]
            return await self._poll_and_download(client, task_id, f"kling_{task_id}.mp4")

    async def generate_transition(
        self, frame_a: Path, frame_b: Path, max_duration_seconds: int
    ) -> GeneratedSegment:
        prompt = "smooth visual transition maintaining consistent style and lighting"
        async with httpx.AsyncClient(timeout=300) as client:
            with open(frame_a, "rb") as fa, open(frame_b, "rb") as fb:
                resp = await client.post(
                    f"{self._base_url}/v1/videos/image2video",
                    headers=self._headers(),
                    files={"start_image": fa, "end_image": fb},
                    data={"prompt": prompt, "duration": min(max_duration_seconds, 4)},
                )
            resp.raise_for_status()
            task_id = resp.json()["data"]["task_id"]
            return await self._poll_and_download(client, task_id, f"kling_transition_{task_id}.mp4")

    async def _poll_and_download(
        self, client: httpx.AsyncClient, task_id: str, filename: str
    ) -> GeneratedSegment:
        dest = self._dir / filename
        while True:
            await asyncio.sleep(5)
            resp = await client.get(
                f"{self._base_url}/v1/videos/{task_id}", headers=self._headers()
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            status = data["task_status"]
            if status == "succeed":
                video_url = data["task_result"]["videos"][0]["url"]
                download = await client.get(video_url)
                dest.write_bytes(download.content)
                return GeneratedSegment(path=dest, duration_seconds=float(data.get("duration", 6)))
            if status == "failed":
                raise RuntimeError(f"Kling generation failed: {data.get('task_status_msg')}")
