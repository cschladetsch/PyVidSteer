from pathlib import Path

from .base import VideoBackend, GeneratedSegment
from .mock import MockBackend
from .kling import KlingBackend
from .runway import RunwayBackend
from .local import LocalBackend

__all__ = ["VideoBackend", "GeneratedSegment", "create_backend"]

_REGISTRY: dict[str, type[VideoBackend]] = {
    "mock": MockBackend,
    "kling": KlingBackend,
    "runway": RunwayBackend,
    "local": LocalBackend,
}


def create_backend(name: str, segments_dir: Path = Path("segments")) -> VideoBackend:
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown backend: {name!r}. Available: {list(_REGISTRY)}")
    return cls(segments_dir=segments_dir)
