This Python project uses UV. Please refer to `pyproject.toml` and `README.md` to understand how to run the code.

## Terminology

- **MMS** — Medoc Main Station, the official Medoc GUI software used to configure and run thermode protocols. The Python API in `examples/medoc-python-api/` bypasses MMS and communicates directly with the hardware over serial.

Refrain from using pip syntax (uv pip install) and use the syntax provided by UV (uv add).

This is a small project - don't worry about backwards compatibility. Feel free to rename/refactor without maintaining legacy aliases.
