# Usage Guide

This guide covers how to run the ramp-and-hold thermal task and the `medoc` control CLI.

## Overview

On each **sequence**, the Medoc MMS thermode ramps from a baseline temperature up to a target,
holds there, then ramps back down to baseline. The participant keeps their eyes on a crosshair; the
word **READY** appears as the temperature ramps up, and during the ramp-down they rate pain
intensity on a 0 (No Pain) – 10 (Worst Pain) trackball slider. The task records the full
temperature stream and the inferred phase transitions.

The task does **not** read the program from MMS. It selects the program and sends `START`, then
*observes* the temperature stream, inferring each phase from the curve. The run file
(`conditions/*.toml`) must therefore mirror the MMS program — see
[MMS Program Parameters](mms-program-parameters.md).

## Launching the Task

```bash
uv run heat-task
```

Options:

| Flag | Effect |
|------|--------|
| `--save-net-events` | Also write `net_events_*.csv` (status-poll failures) alongside the behavioral data, for network diagnostics |

## Setup Wizard

On launch a terminal wizard collects the session parameters. The MMS host/port and screen are
remembered between runs (persisted to `data/.last_connection.json`).

| Prompt | Description | Default |
|--------|-------------|---------|
| **Subject ID** | Participant identifier; used in output filenames | `XXX000` |
| **MMS host/IP** | Address of the Medoc Main Station | last used, else `192.168.1.100` |
| **MMS port** | MMS external-control TCP port | last used, else `20121` |
| **Run file** | A `*.toml` file in `conditions/` | `example.toml` |
| **Screen** | Display index for the PsychoPy window | last used |
| **Show instructions?** | Show the instruction pages before the run | yes |

## Arming MMS and Starting a Run

The task walks you through the MMS sequence on the terminal:

1. Before the window opens, the wizard prompts you to confirm the MMS is ready.
2. The task **selects the program** in MMS (from `program_word` in the run file).
3. Instructions are shown (if enabled), then a crosshair waits on screen.
4. In MMS, click **Pre-test** — **do _not_ click Start**.
5. Press the start key (`0`) in the PsychoPy window. The task sends `START` to MMS automatically, so
   PsychoPy and the thermode begin together.

If the run is interrupted (quit key, Ctrl-C, or an error), the task sends `ABORT` to the thermode
during cleanup; a clean finish sends `STOP`.

## Keyboard Controls

| Key | Action |
|-----|--------|
| `0` (or numpad `0`) | Start the run / dismiss the end screen |
| `1` (or numpad `1`) | Advance instructions |
| Trackball | Move the pain-rating slider during ramp-down |
| `Escape` | Quit at any time |

The pain slider snaps to 11 integer stops (0–10). The participant's last position is recorded
automatically when the rating window (`RATING_TIMEOUT_S`, 15 s) ends.

## Output Files

Each run creates a timestamped directory under `data/`:

```
data/
└── ABC123_example_20260626T143000/
    ├── manifest.json                         # run parameters + system/display info
    ├── behavioral_ABC123_example.csv         # one row per sequence
    ├── temperature_trace_ABC123_example.csv  # one row per status poll
    ├── net_events_ABC123_example.csv         # only with --save-net-events
    └── experiment.log
```

### behavioral CSV (one row per sequence)

| Column | Description |
|--------|-------------|
| `sequence_n` | Sequence number (1-indexed) |
| `baseline_temp` | Baseline temperature (°C) |
| `target_temp` | Target temperature (°C) |
| `ramp_up_onset_s` | Time the ramp-up phase began (s from START) |
| `hold_onset_s` | Time the hold phase began (s) |
| `ramp_down_onset_s` | Time the ramp-down phase began (s) |
| `baseline_return_s` | Time the temperature returned to baseline (s) |
| `rating` | Pain rating (0–10) |
| `rating_no_response` | 1 if no rating was entered before timeout |
| `sequence_end_s` | Time the sequence ended (s) |
| `sample_count` | Number of trace samples recorded in this sequence |

Onset columns hold a time in seconds, or a placeholder string if the phase was never detected.

### temperature_trace CSV (one row per status poll)

One row is written per status poll (~100 Hz), so the trace is the run sampled at the poll rate:
`sample_n`, `time_s`, `sequence_n`, `baseline_temp`, `target_temp`, `raw_temperature`,
`rolling_mean_temperature`, `phase`, `phase_change_event`, `device_system_state`,
`device_test_state`, `device_clock_ms`, `poll_latency_ms`.

### net_events CSV (`--save-net-events` only)

One row per status-poll failure (timeout, decode error, reconnect failure), so otherwise
unexplained gaps in the trace can be attributed after the fact: `time_s`, `cause`, `detail`,
`since_last_sample_s`. See [MMS Networking](mms-networking.md).

## The `medoc` CLI

A standalone client for the MMS external-control protocol, useful for testing the connection and
running programs outside the PsychoPy task. Each command uses a fresh TCP connection because MMS
closes the socket after each command response.

### Monitor

Select a program and monitor MMS status without pretesting or starting:

```bash
uv run medoc monitor 192.168.1.100 15
```

If MMS shows the program as an 8-bit word, pass it directly:

```bash
uv run medoc monitor 192.168.1.100 --program-word 00001111
```

Omit the program ID to monitor without changing the currently selected test.

### Run

Run a configured MMS program and monitor status until it finishes:

```bash
uv run medoc run 192.168.1.100 15
```

`run` follows the Medoc example sequence: select program, send `START` once for pretest, wait
briefly, send `START` again to begin the test, then poll status.

| Flag | Effect |
|------|--------|
| `--port` | MMS TCP port (default 20121) |
| `--poll-interval` | Seconds between status requests (default 1.0) |
| `--connect-timeout` / `--recv-timeout` | Socket timeouts in seconds (default 5.0) |
| `--program-word` | Select by 8-bit word instead of numeric ID, e.g. `00001111` |
| `--select-delay` | Seconds to wait after selecting a program (default 0.5) |
| `--pretest-delay` | Seconds between the pretest `START` and the run `START` (default 1.0) |
| `--no-pretest` | Skip the initial pretest `START` |
| `--wait-for-pretest` | Poll until pretest returns to idle/ready before the run `START` |
| `--pretest-timeout` | Max seconds for `--wait-for-pretest` (default 120.0) |
| `--strict-responses` | Fail if select/pretest/start do not return an immediate response |
| `--count` (monitor) | Stop after this many status responses |

By default, if MMS changes state but a command does not immediately return a response, the CLI
continues; `--strict-responses` makes those missing responses fatal.

Full reference:

```bash
uv run medoc --help
uv run medoc run --help
```

## Quitting Early

Press **Escape** at any point to quit, or **Ctrl-C** in the terminal. The thermode is sent `ABORT`
and any output files written up to that point are saved.
