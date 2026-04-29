from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class BackendConfig:
    primary: str = "mock"
    fallback: list[str] = field(default_factory=list)


@dataclass
class GuardrailConfig:
    profile: str = "default"   # default | adult | art_installation
    age_gate: bool = False


@dataclass
class SessionConfig:
    context_window_tokens: int = 2048
    max_queued_prompts: int = 5


@dataclass
class GenerationConfig:
    target_duration_seconds: int = 6
    transition_max_duration_seconds: int = 4


@dataclass
class Config:
    backend: BackendConfig = field(default_factory=BackendConfig)
    guardrails: GuardrailConfig = field(default_factory=GuardrailConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    redis_url: str = "redis://localhost:6379"
    segments_dir: str = "segments"


def load_config(path: str = "config.yaml") -> Config:
    p = Path(path)
    if not p.exists():
        return Config()

    raw = yaml.safe_load(p.read_text()) or {}
    cfg = Config()

    if "backend" in raw:
        cfg.backend = BackendConfig(**raw["backend"])
    if "guardrails" in raw:
        cfg.guardrails = GuardrailConfig(**raw["guardrails"])
    if "session" in raw:
        cfg.session = SessionConfig(**raw["session"])
    if "generation" in raw:
        cfg.generation = GenerationConfig(**raw["generation"])
    if "redis_url" in raw:
        cfg.redis_url = raw["redis_url"]
    if "segments_dir" in raw:
        cfg.segments_dir = raw["segments_dir"]

    return cfg
