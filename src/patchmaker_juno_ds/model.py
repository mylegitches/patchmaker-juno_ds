"""Human-readable, lossless JUNO-DS patch model."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .errors import PatchValidationError
from .initialization import initialized_blocks
from .spec import (
    BLOCK_BY_KEY,
    BLOCK_SPECS,
    CATEGORIES,
    CATEGORY_OFFSET,
    PATCH_NAME_LENGTH,
    SCHEMA_VERSION,
)
from .parameters import (
    CommonParameters,
    ToneParameters,
    decode_common,
    decode_tone,
    encode_common,
    encode_tone,
    parameters_from_dict,
    parameters_to_dict,
)


def _validate_name(name: object) -> str:
    if not isinstance(name, str):
        raise PatchValidationError("name must be a string")
    if not name or len(name) > PATCH_NAME_LENGTH:
        raise PatchValidationError(f"name must contain 1 to {PATCH_NAME_LENGTH} characters")
    if any(ord(character) < 0x20 or ord(character) > 0x7E for character in name):
        raise PatchValidationError("name must contain printable 7-bit ASCII characters only")
    return name


def _validate_category(category: object) -> int:
    if isinstance(category, bool) or not isinstance(category, int):
        raise PatchValidationError("category must be an integer")
    if not 0 <= category < len(CATEGORIES):
        raise PatchValidationError(f"category must be between 0 and {len(CATEGORIES) - 1}")
    return category


def _validate_blocks(blocks: object) -> dict[str, tuple[int, ...]]:
    if not isinstance(blocks, Mapping):
        raise PatchValidationError("blocks must be an object")
    expected = set(BLOCK_BY_KEY)
    actual = set(blocks)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if extra:
            details.append(f"unknown: {', '.join(str(item) for item in extra)}")
        raise PatchValidationError("invalid patch blocks (" + "; ".join(details) + ")")

    validated: dict[str, tuple[int, ...]] = {}
    for spec in BLOCK_SPECS:
        values = blocks[spec.key]
        if not isinstance(values, (list, tuple)):
            raise PatchValidationError(f"blocks.{spec.key} must be an array")
        if len(values) != spec.size:
            raise PatchValidationError(
                f"blocks.{spec.key} must contain exactly {spec.size} bytes; got {len(values)}"
            )
        clean_values = []
        for index, value in enumerate(values):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0x7F:
                raise PatchValidationError(
                    f"blocks.{spec.key}[{index}] must be a 7-bit integer (0..127)"
                )
            clean_values.append(value)
        validated[spec.key] = tuple(clean_values)
    return validated


@dataclass(frozen=True, slots=True)
class JunoPatch:
    """A complete JUNO-DS temporary patch.

    All nine device blocks are retained losslessly. Name and category are
    exposed as human-readable fields and synchronized into Patch Common.
    """

    name: str
    category: int
    blocks: Mapping[str, tuple[int, ...]]
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise PatchValidationError(
                f"unsupported schema_version {self.schema_version}; expected {SCHEMA_VERSION}"
            )
        name = _validate_name(self.name)
        category = _validate_category(self.category)
        blocks = _validate_blocks(self.blocks)

        common = list(blocks["patch_common"])
        common[:PATCH_NAME_LENGTH] = name.ljust(PATCH_NAME_LENGTH).encode("ascii")
        common[CATEGORY_OFFSET] = category
        blocks["patch_common"] = tuple(common)

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "blocks", blocks)

    @classmethod
    def initialized(cls, name: str = "INIT PATCH", category: int = 0) -> "JunoPatch":
        """Return a complete patch whose bytes have no source-patch ancestry."""
        clean_name = _validate_name(name)
        clean_category = _validate_category(category)
        return cls(clean_name, clean_category, initialized_blocks(clean_name, clean_category))

    @classmethod
    def from_blocks(cls, blocks: Mapping[str, tuple[int, ...] | list[int]]) -> "JunoPatch":
        validated = _validate_blocks(blocks)
        common = validated["patch_common"]
        raw_name = bytes(common[:PATCH_NAME_LENGTH])
        try:
            name = raw_name.decode("ascii").rstrip()
        except UnicodeDecodeError as error:
            raise PatchValidationError("patch name bytes are not 7-bit ASCII") from error
        if not name:
            name = "UNTITLED"
        return cls(name=name, category=common[CATEGORY_OFFSET], blocks=validated)

    @classmethod
    def from_dict(cls, value: object) -> "JunoPatch":
        if not isinstance(value, Mapping):
            raise PatchValidationError("patch document must be a JSON object")
        allowed = {
            "schema_version",
            "device",
            "name",
            "category",
            "category_name",
            "parameters",
            "blocks",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise PatchValidationError(f"unknown top-level field(s): {', '.join(unknown)}")
        if value.get("device", "Roland JUNO-DS") != "Roland JUNO-DS":
            raise PatchValidationError("device must be 'Roland JUNO-DS'")
        category = _validate_category(value.get("category"))
        category_name = value.get("category_name")
        if category_name is not None and category_name != CATEGORIES[category]:
            raise PatchValidationError(
                f"category_name must be {CATEGORIES[category]!r} for category {category}"
            )
        patch = cls(
            name=value.get("name"),  # type: ignore[arg-type]
            category=category,
            blocks=value.get("blocks"),  # type: ignore[arg-type]
            schema_version=value.get("schema_version", SCHEMA_VERSION),  # type: ignore[arg-type]
        )
        if "parameters" in value:
            common, tones = parameters_from_dict(value["parameters"])
            patch = patch.with_parameters(common, tones)
        return patch

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "device": "Roland JUNO-DS",
            "name": self.name,
            "category": self.category,
            "category_name": CATEGORIES[self.category],
            "parameters": parameters_to_dict(self.common_parameters, self.tone_parameters),
            "blocks": {spec.key: list(self.blocks[spec.key]) for spec in BLOCK_SPECS},
        }

    @property
    def common_parameters(self) -> CommonParameters:
        return decode_common(self.blocks["patch_common"])

    @property
    def tone_parameters(self) -> tuple[ToneParameters, ...]:
        mix = self.blocks["tone_mix"]
        return tuple(decode_tone(self.blocks[f"tone_{index + 1}"], mix, index) for index in range(4))

    def with_parameters(
        self, common: CommonParameters, tones: tuple[ToneParameters, ...] | list[ToneParameters]
    ) -> "JunoPatch":
        if len(tones) != 4:
            raise PatchValidationError("exactly four tone parameter sets are required")
        blocks = dict(self.blocks)
        blocks["patch_common"] = encode_common(blocks["patch_common"], common)
        mix = blocks["tone_mix"]
        for index, tone in enumerate(tones):
            block_key = f"tone_{index + 1}"
            blocks[block_key], mix = encode_tone(blocks[block_key], mix, index, tone)
        blocks["tone_mix"] = mix
        return JunoPatch(self.name, self.category, blocks, self.schema_version)

    def with_common_parameters(self, **changes: object) -> "JunoPatch":
        return self.with_parameters(self.common_parameters.updated(**changes), self.tone_parameters)

    def with_tone_parameters(self, tone_number: int, **changes: object) -> "JunoPatch":
        if not 1 <= tone_number <= 4:
            raise PatchValidationError("tone_number must be between 1 and 4")
        tones = list(self.tone_parameters)
        tones[tone_number - 1] = tones[tone_number - 1].updated(**changes)
        return self.with_parameters(self.common_parameters, tones)

    @classmethod
    def load(cls, path: str | Path) -> "JunoPatch":
        try:
            with Path(path).open("r", encoding="utf-8") as handle:
                return cls.from_dict(json.load(handle))
        except json.JSONDecodeError as error:
            raise PatchValidationError(f"invalid JSON: {error}") from error

    def save(self, path: str | Path) -> None:
        with Path(path).open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(self.to_dict(), handle, indent=2)
            handle.write("\n")
