from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GeneratedSegment:
    path: Path
    duration_seconds: float


class VideoBackend(ABC):
    @abstractmethod
    async def generate_from_prompt(self, prompt: str, duration_seconds: int) -> GeneratedSegment:
        ...

    @abstractmethod
    async def generate_transition(
        self,
        frame_a: Path,
        frame_b: Path,
        max_duration_seconds: int,
    ) -> GeneratedSegment:
        ...
