"""Local configuration persistence for Patchmaker."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Mapping

CONFIGURATION_NAMES = (
    "PATCHMAKER_LLM_API_KEY",
    "PATCHMAKER_LLM_BASE_URL",
    "PATCHMAKER_LLM_MODEL",
)


def local_env_path() -> Path:
    override = os.environ.get("PATCHMAKER_ENV_FILE")
    return Path(override).expanduser().resolve() if override else Path.cwd().joinpath(".env").resolve()


def read_local_env(path: Path | None = None) -> dict[str, str]:
    target = path or local_env_path()
    if not target.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, raw_value = line.split("=", 1)
        name = name.removeprefix("export ").strip()
        if name not in CONFIGURATION_NAMES:
            continue
        value = raw_value.strip()
        if value.startswith('"'):
            try:
                parsed = json.loads(value)
                value = parsed if isinstance(parsed, str) else value
            except json.JSONDecodeError:
                pass
        elif len(value) >= 2 and value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        values[name] = value
    return values


def update_local_env(values: Mapping[str, str], path: Path | None = None) -> Path:
    """Atomically update managed values while preserving unrelated `.env` lines."""
    unknown = set(values) - set(CONFIGURATION_NAMES)
    if unknown:
        raise ValueError(f"unsupported configuration name(s): {', '.join(sorted(unknown))}")
    target = path or local_env_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding="utf-8").splitlines() if target.exists() else []
    remaining = dict(values)
    written: set[str] = set()
    output: list[str] = []
    for line in existing:
        stripped = line.strip()
        name = stripped.split("=", 1)[0].removeprefix("export ").strip() if "=" in stripped else ""
        if name in values:
            if name not in written:
                output.append(f"{name}={json.dumps(values[name])}")
                remaining.pop(name, None)
                written.add(name)
        else:
            output.append(line)
    if output and output[-1]:
        output.append("")
    output.extend(f"{name}={json.dumps(value)}" for name, value in remaining.items())
    content = "\n".join(output).rstrip() + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=target.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(content)
    try:
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target
