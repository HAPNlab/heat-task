# heat-task

A PsychoPy ramp-and-hold thermal pain task driven by a [Medoc MMS](https://www.medoc-web.com/)
thermode. Each sequence ramps the thermode from a baseline to a target temperature, holds, then
ramps back down; the participant rates pain on a 0–10 scale during the ramp-down while the task
records the temperature stream.

The task does **not** read the program from MMS — it selects the program, sends `START`, and then
*observes* the thermode's temperature stream, inferring each phase (baseline → ramp-up → hold →
ramp-down → baseline) from the measured curve. A vendored Medoc MMS external-control client
(`medoc`) is included for standalone monitoring and scripted runs.

## Documentation

| Document | Description |
|----------|-------------|
| [Usage Guide](docs/usage.md) | Running the task, the setup wizard, MMS arming sequence, keyboard controls, the `medoc` CLI, and output files |
| [Development Guide](docs/development.md) | Developer setup, co-developing `psyexp-core`, project structure, run files, and key constants |
| [Release Guide](docs/releasing.md) | Versioning (SemVer), verification, and how releases are published |
| [MMS Networking](docs/mms-networking.md) | The external-control protocol and how the status poll loop stays responsive |
| [MMS Program Parameters](docs/mms-program-parameters.md) | How an MMS program maps onto a `conditions/*.toml` run file |

## Quick Start

UV is used for development; Anaconda is the production environment. Both install from the same
`pyproject.toml` — see the [Development Guide](docs/development.md) for details. PsychoPy needs
`psychtoolbox`, which has no arm64 PyPI wheel — install it manually from the lab build (see the
[Development Guide](docs/development.md)).

**UV (development):**

```bash
uv venv
uv sync --inexact
uv run heat-task
```

**Anaconda (production):**

```bash
conda env create -f environment.yml
conda activate heat-task
heat-task
```

Run the task and follow the on-screen MMS arming prompts. To monitor or drive the thermode without
the task, use the `medoc` CLI:

```bash
uv run medoc monitor 192.168.1.100 15   # select program 15 and watch status
uv run medoc run 192.168.1.100 15       # select, start, and monitor a program
```

See the [Usage Guide](docs/usage.md) for the full command reference and options.

## External control reference

Medoc's own walkthrough of the external-control workflow:
https://www.youtube.com/watch?v=itfv7_E__EM&t=700s
