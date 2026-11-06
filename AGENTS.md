This Python project uses UV. Please refer to `pyproject.toml` and `README.md` to understand how to run the code.

## Architecture

This project is a **PsychoPy ramp-and-hold thermal task** driven by a Medoc MMS thermode. It also vendors a small **Medoc MMS external control** client (a Python port of the official MATLAB example in `examples/medoc-external-control/`).

The task package lives in `src/heat_task/`. The root holds the entry point `__main__.py` (console script `heat-task`) and `config.py` (all task constants); everything else is grouped into subpackages:

- `io/` — the input/output boundary: `conditions.py` (TOML run-file loading), `setup_wizard.py` (`run_wizard` + last-connection persistence under `data/`), and `recording.py` (CSV writers + manifest).
- `task/` — the experiment run: `sequence.py` (`run_sequence` + `SequenceRuntime`, which bundles per-run dependencies to avoid prop drilling), `phases.py` (wait-for-start / end screens + key helpers), `rating.py` (`RatingController` slider), `rating_scale.py` (PsychoPy-free rating ↔ slider x mapping), `phase_tracker.py` (`PhaseTracker` — infers the ramp/hold phase from the temperature stream), `status.py` (`StatusPoller` background sampling), `mms.py` (one-off MMS command helpers), `instructions.py`, `display.py`, and `console.py` (the Rich live view).

The Medoc TCP client is a **subpackage** at `src/heat_task/medoc/` (console script `medoc`) with three layers:
- `transport.py` — raw TCP socket (connect/send/recv/close)
- `protocol.py` — wire encoding/decoding (encode_command, decode_response)
- `client.py` — high-level API (MedocClient with named methods per command)
- `models.py` — protocol enums/dataclasses (`Command`, `ReturnCode`, `MedocResponse`, …)
- `cli/` — the `medoc` command line (`parser.py`, `commands.py`, `formatting.py`, `__init__.py` wires `main`)

Task-agnostic experiment plumbing — screen/VSYNC setup, run manifest, CSV writers, setup-wizard primitives, instruction pager, keyboard abstraction — comes from the separate **`psyexp-core`** package, declared as a published PyPI dependency (`psyexp-core>=X.Y`) and pinned exactly in `uv.lock` so clones reproduce. For local co-development overlay an editable sibling checkout (`uv pip install -e ../psyexp-core`) and run with `uv run --no-sync` (or `UV_NO_SYNC=1`, or the `just core-*` recipes). Any sync reverts that overlay because `psyexp-core` is in the lock, including `uv sync --inexact` and the implicit sync in `uv run`, so only skipping the sync preserves it. See "Co-developing `psyexp-core` locally" in `docs/development.md`.

`psychtoolbox` is declared in `pyproject.toml` and comes from PyPI on every platform, including Apple Silicon. Keep the `psychopy` and `psychtoolbox` floors together: older versions of either bring back the arm64 gap, and a failed `psychtoolbox` import silently drops the keyboard to the `event` backend. The manual lab wheel is a backup only and follows the same `--no-sync` rule (see `docs/development.md`).

## Terminology

- **MMS** — Medoc Main Station, the official Medoc GUI software used to configure and run thermode protocols.
- **External control** — the TCP socket API exposed by MMS (default port 20121) that allows remote software to send commands and receive status responses.

## Guidelines

Refrain from using pip syntax (uv pip install) and use the syntax provided by UV (uv add).

This is a small project — don't worry about backwards compatibility. Feel free to rename/refactor without maintaining legacy aliases.
