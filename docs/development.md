# Development Guide

This guide covers setting up and developing `heat-task`.

## Prerequisites

- Python 3.11 (the project pins `>=3.11,<3.12`)
- One of:
  - [UV](https://docs.astral.sh/uv/) — fast Python package installer and resolver (**development**)
  - [Anaconda / Miniconda](https://docs.conda.io/) (**production** deployment environment)
- A Medoc MMS thermode (or the `medoc` CLI against a reachable MMS) for live runs
- macOS or Windows (PsychoPy supports both)

### macOS

PsychoPy's heavy binary libs build more reliably with these installed (the conda env provides the
equivalents):

```bash
brew install hdf5 openblas lapack
```

### psychtoolbox

`psychtoolbox` is **not** declared in `pyproject.toml`: PyPI has no arm64 wheel for it. On Apple
Silicon, install it manually from the lab build, e.g.

```bash
uv pip install ../Psychtoolbox-3/dist/psychtoolbox-3.0.22.2-cp311-cp311-macosx_10_9_universal2.whl
```

Because `uv sync` is exact by default it removes the manual install — run it as `uv sync --inexact`
to keep psychtoolbox. (`uv run`'s implicit sync is *inexact*, so it leaves the manual install alone;
pass `--no-sync` only when you are also overlaying an editable `psyexp-core`, which *is* in the lock
and would otherwise be reverted.) On Windows the lab build is needed similarly; otherwise PsychoPy's
own transitive `psychtoolbox` (`<3.0.20`, non-arm64) applies.

## Quick Start

UV is the development workflow; Anaconda is the production run environment. Both install the package
from the same `pyproject.toml`.

### UV (development)

```bash
uv venv
uv sync --inexact
uv run heat-task
```

### Anaconda / conda (production)

Conda provisions Python (and the heavy binary libs), then pip installs the package from
`pyproject.toml`:

```bash
conda env create -f environment.yml
conda activate heat-task
heat-task
```

Or into an existing/custom environment:

```bash
conda create -n heat python=3.11
conda activate heat
pip install -e ".[dev]"
```

`pyproject.toml` is the shared, standard manifest. The UV-specific pieces (`[tool.uv.*]`, `uv.lock`)
are ignored by pip/conda, so the conda install resolves dependencies fresh from PyPI rather than
from the lockfile. `psychtoolbox` is still not pulled in automatically (see below) — install the lab
build manually after creating the environment.

> **Heads up — `uv run` auto-syncs the venv from `uv.lock` on every launch** (inexactly: it won't
> remove your manually-installed psychtoolbox, but it *will* revert a local editable `psyexp-core`
> back to the locked PyPI version, since the core is in the lock). While co-developing the core,
> skip that sync with `UV_NO_SYNC=1` — `export` it in your shell, prefix commands with
> `uv run --no-sync …`, or use the `just core-*` recipes.

## Co-developing `psyexp-core` locally

Task-agnostic experiment plumbing — screen/VSYNC setup, run manifest, CSV writers, setup-wizard
primitives, instruction pager, keyboard abstraction — comes from the separate
[`psyexp-core`](../../psyexp-core) package. `pyproject.toml` declares it as a published PyPI
dependency (`psyexp-core>=X.Y`); the exact version is pinned in `uv.lock` so clones reproduce.

To work on it from the sibling checkout, overlay an editable install (it sticks as long as the
re-sync that would revert it is skipped):

```bash
export UV_NO_SYNC=1                 # for this shell; required so the overlay sticks
uv pip install -e ../psyexp-core    # one time
uv run heat-task                    # uses your local core, edits are live
```

The `just core-dev` / `just core-run` / `just core-test` recipes wrap this — they overlay the
editable checkout and run with `--no-sync`. Note `uv sync --inexact` does **not** preserve the
editable core: `--inexact` only spares packages absent from the lock (that's what keeps
psychtoolbox), and the core *is* in the lock, so only skipping the sync keeps it. After changing
*other* dependencies you'll need a manual `uv sync --inexact` — that reverts psyexp-core, so re-run
the editable install (or `just core-dev`) afterward.

For a setup that survives sync, declare the path source in `pyproject.toml`
(`[tool.uv.sources] psyexp-core = { path = "../psyexp-core", editable = true }`) and keep that edit
local with `git update-index --skip-worktree pyproject.toml uv.lock`.

## Updating `psyexp-core`

`psyexp-core` is a published PyPI dependency (`psyexp-core>=X.Y` in `pyproject.toml`). A bare
`uv sync` does **not** pull a newer release — it installs exactly what `uv.lock` pins, so a newly
published version is ignored until the lock is regenerated. To upgrade:

```bash
uv lock --upgrade-package psyexp-core   # rewrite uv.lock to the newest version the constraint allows
uv sync --inexact                       # apply it; --inexact keeps the manual psychtoolbox install
```

(`just core-upgrade` runs both commands.) Then commit the updated `uv.lock`. Raise the `>=` floor in `pyproject.toml` first if you want to
require a new minimum. CI (`.github/workflows/tests.yml`) reads the pinned version straight from
`uv.lock` via `uv export --frozen`, so it tracks the upgrade automatically once the lock is
committed.

## Guidelines

- Use UV's own syntax (`uv add`) rather than pip syntax (`uv pip install`) for managing
  dependencies, except for the manual psychtoolbox/editable-core overlays documented above.
- This is a small project — don't worry about backwards compatibility. Rename/refactor freely
  without maintaining legacy aliases.

## Project Structure

```
heat-task/
├── src/
│   └── heat_task/
│       ├── __main__.py        # Entry point (heat-task); wires the run top-to-bottom
│       ├── config.py          # All task constants (no cross-module imports)
│       ├── io/                # Input/output boundary
│       │   ├── conditions.py      # TOML run-file loading + validation
│       │   ├── setup_wizard.py    # run_wizard + last-connection persistence
│       │   └── recording.py       # CSV writers + manifest
│       ├── task/              # The experiment run + on-screen presentation
│       │   ├── sequence.py        # run_sequences + SequenceRuntime
│       │   ├── phases.py          # wait-for-start / end screens + key helpers
│       │   ├── rating.py          # RatingController slider
│       │   ├── phase_tracker.py   # PhaseTracker — infers ramp/hold phase from the stream
│       │   ├── status.py          # StatusPoller background sampling
│       │   ├── mms.py             # One-off MMS command helpers
│       │   ├── framerate.py       # Frame-rate resolution
│       │   ├── instructions.py    # Instruction presentation
│       │   ├── display.py         # PsychoPy stimuli construction
│       │   └── console.py         # Rich live-view
│       └── medoc/             # Vendored MMS external-control client (medoc CLI)
│           ├── transport.py       # Raw TCP socket (connect/send/recv/close)
│           ├── protocol.py        # Wire encoding/decoding
│           ├── client.py          # High-level MedocClient API
│           ├── models.py          # Protocol enums/dataclasses
│           └── cli/               # The medoc command line
├── conditions/                # TOML run files (example.toml)
├── examples/                  # Reference material (Medoc external-control MATLAB example)
├── data/                      # Output directory (created at runtime)
├── docs/
├── tests/
└── pyproject.toml
```

## Module Overview

| Module | Responsibility |
|--------|---------------|
| `config.py` | Single source of truth for all constants: polling, phase-tracker thresholds, slider geometry, keys |
| `task/` | The experiment run: `sequence.py` loop, the `phase_tracker.py` state machine, `status.py` poller, on-screen `display.py`/`instructions.py`/`rating.py`, and the `console.py` live view |
| `io/` | The I/O boundary: `conditions.py` run-file loading, `setup_wizard.py`, and `recording.py` (CSV writers + manifest) |
| `medoc/` | The vendored MMS client and `medoc` CLI (a Python port of the official MATLAB example in `examples/`) |
| `__main__.py` | Orchestration: wizard → MMS select → instructions → wait for start → poller + sequence loop → cleanup |

## Run Files (`conditions/*.toml`)

A run file declares the MMS program word and one `[[sequence]]` table per MMS program column. Field
names mirror the MMS columns (baseline → ramp-up → hold → ramp-down → trailing baseline). See
[MMS Program Parameters](mms-program-parameters.md) for the full mapping.

```toml
program_word = "00001111"          # 8-bit MMS program word

[[sequence]]
baseline = 35.0
time_before_s = 20.0               # MMS "Time Before Sequence" lead-in (default 0)
target_temp = 46.0                 # must be greater than baseline
target_hold_duration_s = 30.0      # hold at target before ramp-down
baseline_duration_s = 30.0         # trailing baseline after ramp-down (the MMS ISI)
```

Validation (`io/conditions.py`): `program_word` must be exactly 8 bits, each sequence's
`target_temp` must exceed its `baseline`, and at least one `[[sequence]]` is required.

## Key Constants (`config.py`)

| Constant | Value | Description |
|----------|-------|-------------|
| `POLL_INTERVAL_S` | `0.01` | Min gap between status polls (~100 Hz) |
| `POLL_RECV_TIMEOUT_S` | `0.5` | Reply deadline for the status poller's socket |
| `SMOOTHING_WINDOW` | `5` | Samples averaged for the smoothed temperature |
| `TREND_WINDOW` | `4` | Samples averaged for the slope / trend direction |
| `CONSECUTIVE_SAMPLES` | `3` | Debounce: polls a transition condition must hold before firing |
| `BASELINE_TOLERANCE` | `0.40` | °C window around baseline counted as "at baseline" |
| `TARGET_TOLERANCE` | `0.50` | °C window around target counted as "at target" |
| `RAMP_START_DELTA` | `0.30` | °C rise above baseline that marks ramp-up onset |
| `RAMP_DOWN_DELTA` | `0.35` | °C fall below peak that marks ramp-down onset |
| `PRIME_WINDOW_S` | `3.0` | How far ahead of a scheduled event the tighter "primed" thresholds kick in |
| `RATING_TIMEOUT_S` | `15.0` | Time the participant has to enter a pain rating |
| `RATING_MIN` / `RATING_MAX` | `0` / `10` | Pain-rating scale bounds (11 integer stops) |

The phase tracker never sees the thermode's command schedule — it infers every transition from the
measured temperature curve. `config.py` documents the full state machine and the "primed"
overrides; see also [MMS Networking](mms-networking.md).

## Testing

```bash
uv run pytest
```

CI (`.github/workflows/tests.yml`) runs the suite headless **without PsychoPy** — the medoc and
ramp/hold modules the tests exercise are import-clean without it. `psyexp-core` is installed
`--no-deps` (its pinned version read from `uv.lock`), and `tests/test_ramp_hold_recorder.py` is
excluded because it imports the setup wizard, which pulls in PsychoPy at import time.

## Terminology

- **MMS** — Medoc Main Station, the official Medoc GUI used to configure and run thermode protocols.
- **External control** — the TCP socket API exposed by MMS (default port 20121) that lets remote
  software send commands and receive status responses.
