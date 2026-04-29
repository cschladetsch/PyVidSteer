from __future__ import annotations
import asyncio
import os
from pathlib import Path

import httpx

from .base import VideoBackend, GeneratedSegment


class LocalBackend(VideoBackend):
    """
    ComfyUI + Stable Video Diffusion backend.
    Requires a running ComfyUI instance.
    Set COMFYUI_URL to point at it (default: http://localhost:8188).
    Adapt the workflow dicts in _build_*_workflow to match your node setup.
    """

    def __init__(self, segments_dir: Path = Path("segments")):
        self._comfyui_url = os.environ.get("COMFYUI_URL", "http://localhost:8188")
        self._dir = segments_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    async def generate_from_prompt(self, prompt: str, duration_seconds: int) -> GeneratedSegment:
        workflow = _build_txt2vid_workflow(prompt, duration_seconds)
        slug = abs(hash(prompt)) % 100_000
        return await self._execute_workflow(workflow, f"local_{slug:05d}.mp4")

    async def generate_transition(
        self, frame_a: Path, frame_b: Path, max_duration_seconds: int
    ) -> GeneratedSegment:
        workflow = _build_img2vid_workflow(frame_a, max_duration_seconds)
        slug = abs(hash(str(frame_a))) % 100_000
        return await self._execute_workflow(workflow, f"local_transition_{slug:05d}.mp4")

    async def _execute_workflow(self, workflow: dict, filename: str) -> GeneratedSegment:
        dest = self._dir / filename
        async with httpx.AsyncClient(timeout=600) as client:
            resp = await client.post(
                f"{self._comfyui_url}/prompt", json={"prompt": workflow}
            )
            resp.raise_for_status()
            prompt_id = resp.json()["prompt_id"]

            while True:
                await asyncio.sleep(3)
                history_resp = await client.get(f"{self._comfyui_url}/history/{prompt_id}")
                history = history_resp.json()
                if prompt_id not in history or not history[prompt_id].get("outputs"):
                    continue

                outputs = history[prompt_id]["outputs"]
                video_node = next(iter(outputs.values()))
                videos = video_node.get("gifs") or video_node.get("videos") or []
                if not videos:
                    break

                vid = videos[0]
                file_resp = await client.get(
                    f"{self._comfyui_url}/view",
                    params={
                        "filename": vid["filename"],
                        "subfolder": vid.get("subfolder", ""),
                        "type": "output",
                    },
                )
                dest.write_bytes(file_resp.content)
                fps = vid.get("frame_rate", 8)
                frames = vid.get("frame_count", 48)
                return GeneratedSegment(path=dest, duration_seconds=frames / max(fps, 1))

        raise RuntimeError(f"ComfyUI workflow {prompt_id} produced no video output")


def _build_txt2vid_workflow(prompt: str, duration_seconds: int) -> dict:
    # Minimal skeleton -- adapt node IDs and connections to your ComfyUI setup.
    return {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "svd_xt.safetensors"}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
    }


def _build_img2vid_workflow(frame: Path, duration_seconds: int) -> dict:
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": str(frame)}},
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "svd_xt.safetensors"}},
    }
