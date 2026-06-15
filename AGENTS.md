This Python project uses UV. Please refer to `pyproject.toml` and `README.md` to understand how to run the code.

## Architecture

This project is a **PsychoPy ramp-and-hold thermal task** driven by a Medoc MMS thermode. It also vendors a small **Medoc MMS external control** client (a Python port of the official MATLAB example in `examples/medoc-external-control/`).

The task package lives in `src/heat_task/` — entry point `__main__.py` (console script `heat-task`), plus `session.py` (setup wizard + instructions), `trial.py`, `detector.py`, `display.py`, `recorder.py`, `conditions.py`, and `config.py`.

The Medoc TCP client is a **subpackage** at `src/heat_task/medoc/` (console script `medoc`) with three layers:
- `transport.py` — raw TCP socket (connect/send/recv/close)
- `protocol.py` — wire encoding/decoding (encode_command, decode_response)
- `client.py` — high-level API (MedocClient with named methods per command)

Task-agnostic experiment plumbing — screen/VSYNC setup, run manifest, CSV writers, setup-wizard primitives, instruction pager, keyboard abstraction — comes from the separate **`psyexp-core`** package (consumed via an editable path source in dev; see `[tool.uv.sources]` in `pyproject.toml`).

## Terminology

- **MMS** — Medoc Main Station, the official Medoc GUI software used to configure and run thermode protocols.
- **External control** — the TCP socket API exposed by MMS (default port 20121) that allows remote software to send commands and receive status responses.

## Guidelines

Refrain from using pip syntax (uv pip install) and use the syntax provided by UV (uv add).

This is a small project — don't worry about backwards compatibility. Feel free to rename/refactor without maintaining legacy aliases.
