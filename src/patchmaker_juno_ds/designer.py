"""Provider-neutral text-to-patch and patch-refinement orchestration."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Mapping, Protocol, runtime_checkable

from .errors import PatchValidationError, PlannerError
from .model import JunoPatch
from .parameters import CommonParameters, ToneParameters

_COMMON_FIELDS = frozenset(field.name for field in fields(CommonParameters))
_TONE_FIELDS = frozenset(field.name for field in fields(ToneParameters))


def _changes(value: object, label: str, allowed: frozenset[str]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise PatchValidationError(f"{label} must be an object")
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise PatchValidationError(f"unknown {label} field(s): {', '.join(unknown)}")
    return dict(value)


@dataclass(frozen=True, slots=True)
class ToneChange:
    tone_number: int
    changes: Mapping[str, object]

    def __post_init__(self) -> None:
        if isinstance(self.tone_number, bool) or not isinstance(self.tone_number, int):
            raise PatchValidationError("tone_number must be an integer")
        if not 1 <= self.tone_number <= 4:
            raise PatchValidationError("tone_number must be between 1 and 4")
        clean = _changes(self.changes, f"tone {self.tone_number} changes", _TONE_FIELDS)
        if not clean:
            raise PatchValidationError(f"tone {self.tone_number} changes may not be empty")
        object.__setattr__(self, "changes", clean)


@dataclass(frozen=True, slots=True)
class PatchChangePlan:
    """A validated semantic plan produced by an LLM or another planner."""

    explanation: str
    name: str | None = None
    category: int | None = None
    common: Mapping[str, object] | None = None
    tones: tuple[ToneChange, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise PatchValidationError("plan explanation must be a non-empty string")
        if self.name is not None and not isinstance(self.name, str):
            raise PatchValidationError("plan name must be a string or null")
        if self.category is not None and (
            isinstance(self.category, bool) or not isinstance(self.category, int)
        ):
            raise PatchValidationError("plan category must be an integer or null")
        if self.common is not None:
            object.__setattr__(
                self, "common", _changes(self.common, "common changes", _COMMON_FIELDS)
            )
        tone_numbers = [tone.tone_number for tone in self.tones]
        if len(tone_numbers) != len(set(tone_numbers)):
            raise PatchValidationError("a plan may change each tone at most once")
        if self.name is None and self.category is None and not self.common and not self.tones:
            raise PatchValidationError("plan does not contain any patch changes")

    @classmethod
    def from_dict(cls, value: object) -> "PatchChangePlan":
        if not isinstance(value, Mapping):
            raise PatchValidationError("planner response must be a JSON object")
        allowed = {"explanation", "name", "category", "common", "tones"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise PatchValidationError(f"unknown plan field(s): {', '.join(unknown)}")
        tones_value = value.get("tones", [])
        if not isinstance(tones_value, list):
            raise PatchValidationError("plan tones must be an array")
        tones: list[ToneChange] = []
        for index, tone in enumerate(tones_value):
            if not isinstance(tone, Mapping) or set(tone) != {"tone_number", "changes"}:
                raise PatchValidationError(
                    f"plan tones[{index}] must contain exactly tone_number and changes"
                )
            tones.append(ToneChange(tone["tone_number"], tone["changes"]))  # type: ignore[arg-type]
        return cls(
            explanation=value.get("explanation"),  # type: ignore[arg-type]
            name=value.get("name"),  # type: ignore[arg-type]
            category=value.get("category"),  # type: ignore[arg-type]
            common=value.get("common"),  # type: ignore[arg-type]
            tones=tuple(tones),
        )

    def apply(self, patch: JunoPatch) -> JunoPatch:
        """Apply through the verified model, which enforces every device range."""
        result = JunoPatch(
            name=self.name if self.name is not None else patch.name,
            category=self.category if self.category is not None else patch.category,
            blocks=patch.blocks,
            schema_version=patch.schema_version,
        )
        if self.common:
            result = result.with_common_parameters(**self.common)
        for tone in self.tones:
            result = result.with_tone_parameters(tone.tone_number, **tone.changes)
        return result


@runtime_checkable
class PatchPlanner(Protocol):
    def create_plan(self, request: str, patch: JunoPatch) -> PatchChangePlan: ...


@dataclass(frozen=True, slots=True)
class RefinementResult:
    patch: JunoPatch
    plan: PatchChangePlan


class SoundDesigner:
    def __init__(self, planner: PatchPlanner) -> None:
        if not isinstance(planner, PatchPlanner):
            raise TypeError("planner must implement create_plan(request, patch)")
        self.planner = planner

    def refine(self, patch: JunoPatch, request: str) -> RefinementResult:
        if not isinstance(request, str) or not request.strip():
            raise PatchValidationError("sound-design request must be a non-empty string")
        if len(request) > 4000:
            raise PatchValidationError("sound-design request may not exceed 4000 characters")
        try:
            plan = self.planner.create_plan(request.strip(), patch)
            return RefinementResult(patch=plan.apply(patch), plan=plan)
        except PatchValidationError:
            raise
        except Exception as error:
            raise PlannerError(f"sound-design planner failed: {error}") from error
