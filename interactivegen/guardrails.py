from __future__ import annotations
from dataclasses import dataclass
from .models import GuardrailVerdict


_DEFAULT_BLOCKED: frozenset[str] = frozenset({
    "violence", "gore", "kill", "murder", "weapon", "gun", "bomb",
    "child", "minor", "underage",
    "hate", "racist", "slur",
})

# Adult profile relaxes content restrictions but keeps hard limits
_ADULT_BLOCKED: frozenset[str] = frozenset({
    "child", "minor", "underage",
    "gore", "snuff",
})

# Art installation profile -- minimal restrictions, hard limits only
_ART_BLOCKED: frozenset[str] = frozenset({
    "child", "minor", "underage",
})

_PROFILE_RULES: dict[str, frozenset[str]] = {
    "default": _DEFAULT_BLOCKED,
    "adult": _ADULT_BLOCKED,
    "art_installation": _ART_BLOCKED,
}


@dataclass
class GuardrailLayer:
    profile: str = "default"

    def classify(self, prompt: str) -> tuple[GuardrailVerdict, str | None]:
        blocked = _PROFILE_RULES.get(self.profile, _DEFAULT_BLOCKED)
        lowered = prompt.lower()
        for term in blocked:
            if term in lowered:
                return GuardrailVerdict.REJECTED, f"Content blocked under profile '{self.profile}'"
        return GuardrailVerdict.APPROVED, None
