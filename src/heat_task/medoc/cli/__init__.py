"""Command line interface for Medoc MMS external control.

The CLI is split across this package: ``parser`` builds the argument parser,
``commands`` holds the ``run``/``monitor`` implementations, and ``formatting``
holds the response/output helpers. ``main`` wires them together.
"""

from __future__ import annotations

from collections.abc import Sequence

from heat_task.medoc.cli.commands import monitor_status, run_program
from heat_task.medoc.cli.parser import build_parser

# Re-exported so callers (and tests) can reach the client through the CLI module.
from heat_task.medoc.client import MedocClient

__all__ = ["MedocClient", "build_parser", "main", "monitor_status", "run_program"]


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
