"""Persistent local history for generated JUNO-DS patches."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .errors import PatchValidationError
from .model import JunoPatch
from .spec import CATEGORIES

LIBRARY_SCHEMA_VERSION = 1


def default_library_path() -> Path:
    override = os.environ.get("PATCHMAKER_LIBRARY_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path.cwd().joinpath(".patchmaker", "patches").resolve()


@dataclass(frozen=True, slots=True)
class PatchRecord:
    id: str
    created_at: str
    request: str
    explanation: str
    patch: JunoPatch
    parent_id: str | None = None

    def summary(self) -> dict[str, object]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "name": self.patch.name,
            "category": self.patch.category,
            "category_name": CATEGORIES[self.patch.category],
            "request": self.request,
            "explanation": self.explanation,
            "parent_id": self.parent_id,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "library_schema_version": LIBRARY_SCHEMA_VERSION,
            **self.summary(),
            "patch": self.patch.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: object) -> "PatchRecord":
        if not isinstance(value, dict):
            raise PatchValidationError("patch history record must be an object")
        required = {
            "library_schema_version", "id", "created_at", "request", "explanation",
            "name", "category", "category_name", "parent_id", "patch",
        }
        if set(value) != required:
            raise PatchValidationError("patch history record has invalid fields")
        if value["library_schema_version"] != LIBRARY_SCHEMA_VERSION:
            raise PatchValidationError("unsupported patch history schema")
        record_id = _valid_id(value["id"], "id")
        parent = value["parent_id"]
        parent_id = None if parent is None else _valid_id(parent, "parent_id")
        for name in ("created_at", "request", "explanation"):
            if not isinstance(value[name], str) or not value[name]:
                raise PatchValidationError(f"patch history {name} must be a non-empty string")
        patch = JunoPatch.from_dict(value["patch"])
        if value["name"] != patch.name or value["category"] != patch.category:
            raise PatchValidationError("patch history summary does not match patch")
        if value["category_name"] != CATEGORIES[patch.category]:
            raise PatchValidationError("patch history category name does not match patch")
        return cls(
            id=record_id,
            created_at=value["created_at"],
            request=value["request"],
            explanation=value["explanation"],
            patch=patch,
            parent_id=parent_id,
        )


def _valid_id(value: object, name: str = "record id") -> str:
    if not isinstance(value, str):
        raise PatchValidationError(f"{name} must be a UUID")
    try:
        parsed = uuid.UUID(value)
    except ValueError as error:
        raise PatchValidationError(f"{name} must be a UUID") from error
    if str(parsed) != value.lower():
        raise PatchValidationError(f"{name} must be a canonical UUID")
    return str(parsed)


class PatchLibrary:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or default_library_path()).resolve()

    def save(
        self,
        patch: JunoPatch,
        *,
        request: str,
        explanation: str,
        parent_id: str | None = None,
    ) -> PatchRecord:
        if parent_id is not None:
            _valid_id(parent_id, "parent_id")
        record = PatchRecord(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            request=request,
            explanation=explanation,
            patch=patch,
            parent_id=parent_id,
        )
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root.joinpath(f"{record.id}.json")
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=self.root, delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(record.to_dict(), handle, indent=2)
            handle.write("\n")
        try:
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
        return record

    def load(self, record_id: str) -> PatchRecord:
        clean_id = _valid_id(record_id)
        target = self.root.joinpath(f"{clean_id}.json")
        if not target.is_file():
            raise PatchValidationError("saved patch was not found")
        try:
            return PatchRecord.from_dict(json.loads(target.read_text(encoding="utf-8")))
        except json.JSONDecodeError as error:
            raise PatchValidationError("saved patch record contains invalid JSON") from error

    def list(self) -> list[dict[str, object]]:
        if not self.root.is_dir():
            return []
        records: list[PatchRecord] = []
        for path in self.root.glob("*.json"):
            try:
                records.append(PatchRecord.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError, PatchValidationError):
                continue
        records.sort(key=lambda record: (record.created_at, record.id), reverse=True)
        return [record.summary() for record in records]
