This Python project uses UV. Please refer to `pyproject.toml` and `README.md` to understand how to run the code.

## Terminology

- **MMS** — Medoc Main Station, the official Medoc GUI software used to configure and run thermode protocols. The Python API in `examples/medoc-python-api/` bypasses MMS and communicates directly with the hardware over serial.

Refrain from using pip syntax (uv pip install) and use the syntax provided by UV (uv add).

This is a small project - don't worry about backwards compatibility. Feel free to rename/refactor without maintaining legacy aliases.

## Mock device

`MockTsaDevice` must expose exactly the same public API as `TsaDevice` — no mock-only properties or methods. Any attribute the runner or other code reads from the device must exist on both classes. If new state needs to be surfaced (e.g. for the status panel), add it to `TsaDevice` first and derive it from real serial data, then implement the same property/attribute on `MockTsaDevice`.

The mock should be indistinguishable from production at the UI and runner level. All status fields (temperatures, health, tokens, state) must be simulated with realistic values so the console output looks identical whether running against hardware or the mock.
