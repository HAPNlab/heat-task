This Python project uses UV. Please refer to `pyproject.toml` and `README.md` to understand how to run the code.

## Architecture

This library implements the **Medoc MMS external control interface** — a TCP-based protocol for controlling the Medoc Main Station (MMS) software. It is a Python port of the official MATLAB external control example in `examples/medoc-external-control/`.

The library lives in `src/medoc/` and has three layers:
- `transport.py` — raw TCP socket (connect/send/recv/close)
- `protocol.py` — wire encoding/decoding (encode_command, decode_response)
- `client.py` — high-level API (MedocClient with named methods per command)

## Terminology

- **MMS** — Medoc Main Station, the official Medoc GUI software used to configure and run thermode protocols.
- **External control** — the TCP socket API exposed by MMS (default port 20121) that allows remote software to send commands and receive status responses.

## Guidelines

Refrain from using pip syntax (uv pip install) and use the syntax provided by UV (uv add).

This is a small project — don't worry about backwards compatibility. Feel free to rename/refactor without maintaining legacy aliases.
