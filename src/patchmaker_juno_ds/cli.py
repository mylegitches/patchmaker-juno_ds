"""Command-line interface for file conversion and optional hardware I/O."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .client import JunoClient
from .codec import decode_edit_buffer, encode_edit_buffer
from .designer import SoundDesigner
from .errors import PatchmakerError, PlannerError
from .gui import serve_gui
from .mido_transport import MidoTransport, port_names
from .model import JunoPatch
from .openai_compatible import OpenAICompatiblePlanner


def _device_id(value: str) -> int:
    try:
        parsed = int(value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError("device ID must be an integer such as 16 or 0x10") from error
    if not 0 <= parsed <= 0x1F:
        raise argparse.ArgumentTypeError("device ID must be between 0 and 31")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="patchmaker-juno", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate a patch JSON file")
    validate.add_argument("patch", type=Path)

    to_json = commands.add_parser("syx-to-json", help="convert a complete edit-buffer .syx dump")
    to_json.add_argument("input", type=Path)
    to_json.add_argument("output", type=Path)

    to_syx = commands.add_parser("json-to-syx", help="encode patch JSON as edit-buffer DT1 messages")
    to_syx.add_argument("input", type=Path)
    to_syx.add_argument("output", type=Path)
    to_syx.add_argument("--device-id", type=_device_id, default=0x10)

    refine = commands.add_parser("refine", help="refine a patch through an OpenAI-compatible LLM")
    refine.add_argument("input", type=Path)
    refine.add_argument("request", help="natural-language sound-design request")
    refine.add_argument("output", type=Path)
    refine.add_argument("--base-url", default=os.environ.get("PATCHMAKER_LLM_BASE_URL"))
    refine.add_argument("--model", default=os.environ.get("PATCHMAKER_LLM_MODEL"))
    refine.add_argument("--timeout", type=float, default=60.0)

    gui = commands.add_parser("gui", help="open the local browser interface")
    gui.add_argument("--port", type=int, default=8765)
    gui.add_argument("--no-browser", action="store_true")

    commands.add_parser("list-ports", help="list MIDI ports (requires the midi extra)")

    read = commands.add_parser("read", help="read the current patch from a JUNO-DS")
    read.add_argument("output", type=Path)
    read.add_argument("--input-port", required=True)
    read.add_argument("--output-port", required=True)
    read.add_argument("--device-id", type=_device_id, default=0x10)

    write = commands.add_parser("write", help="write JSON to the temporary edit buffer")
    write.add_argument("input", type=Path)
    write.add_argument("--input-port", required=True)
    write.add_argument("--output-port", required=True)
    write.add_argument("--device-id", type=_device_id, default=0x10)
    write.add_argument(
        "--confirm-temporary-write",
        action="store_true",
        help="required safety acknowledgement; this does not save a user patch",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            patch = JunoPatch.load(args.patch)
            print(f"Valid JUNO-DS patch: {patch.name} ({patch.category})")
        elif args.command == "syx-to-json":
            patch = decode_edit_buffer(args.input.read_bytes())
            patch.save(args.output)
            print(f"Wrote {args.output}")
        elif args.command == "json-to-syx":
            patch = JunoPatch.load(args.input)
            args.output.write_bytes(b"".join(encode_edit_buffer(patch, args.device_id)))
            print(f"Wrote {args.output}")
        elif args.command == "refine":
            if not args.base_url:
                raise PlannerError("set --base-url or PATCHMAKER_LLM_BASE_URL")
            if not args.model:
                raise PlannerError("set --model or PATCHMAKER_LLM_MODEL")
            planner = OpenAICompatiblePlanner(
                base_url=args.base_url,
                model=args.model,
                api_key=os.environ.get("PATCHMAKER_LLM_API_KEY"),
                timeout=args.timeout,
            )
            result = SoundDesigner(planner).refine(JunoPatch.load(args.input), args.request)
            result.patch.save(args.output)
            print(result.plan.explanation)
            print(f"Wrote {args.output}")
        elif args.command == "gui":
            serve_gui(port=args.port, open_browser=not args.no_browser)
        elif args.command == "list-ports":
            inputs, outputs = port_names()
            print("Inputs:")
            for name in inputs:
                print(f"  {name}")
            print("Outputs:")
            for name in outputs:
                print(f"  {name}")
        elif args.command == "read":
            with MidoTransport(args.input_port, args.output_port) as transport:
                patch = JunoClient(transport, device_id=args.device_id).read_current_patch()
            patch.save(args.output)
            print(f"Read {patch.name!r} and wrote {args.output}")
        elif args.command == "write":
            if not args.confirm_temporary_write:
                print(
                    "Refusing hardware write without --confirm-temporary-write",
                    file=sys.stderr,
                )
                return 2
            patch = JunoPatch.load(args.input)
            with MidoTransport(args.input_port, args.output_port) as transport:
                JunoClient(transport, device_id=args.device_id).write_temporary_patch(patch)
            print(f"Sent {patch.name!r} to the temporary edit buffer")
        return 0
    except (PatchmakerError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
