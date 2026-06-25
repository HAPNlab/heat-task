Watch this for external control: https://www.youtube.com/watch?v=itfv7_E__EM&t=700s

## CLI

Select a program and monitor MMS status without pretesting or starting:

```bash
uv run medoc monitor 192.168.1.100 15
```

If MMS shows the program as an 8-bit word, pass it directly:

```bash
uv run medoc monitor 192.168.1.100 --program-word 00001111
```

To monitor without changing the currently selected test, omit the program ID.

Run a configured MMS program/test and monitor status until it finishes:

```bash
uv run medoc run 192.168.1.100 15
```

The run command follows the Medoc example sequence: select program, send `START` once for
pretest, wait briefly, send `START` again to begin the test, then poll status. Each command
uses a fresh TCP connection because MMS closes connections after command responses.

If MMS changes state but a command does not immediately return a response, the CLI continues.
Use `--strict-responses` to fail on missing select/pretest/start responses. Use `--no-pretest`
to skip the initial pretest `START`.

Use `--wait-for-pretest` if you specifically want to wait until MMS reports idle/ready before
sending the second `START`.

Options:

```bash
uv run medoc run --help
```

## PsychoPy Ramp/Hold Task

Run the PsychoPy ramp-and-hold task with:

```bash
uv run heat-task
```

> **Heads up — `uv run` auto-syncs the venv from `uv.lock` on every launch.** That
> sync will (a) revert a local editable `psyexp-core` back to the pinned git tag and
> (b) remove the manually-installed Apple Silicon psychtoolbox wheel. Disable it by
> setting `UV_NO_SYNC=1` — either `export UV_NO_SYNC=1` in your shell session or
> prefix individual commands with `uv run --no-sync …`.

### Co-developing `psyexp-core` locally

The shared harness is pinned to a git tag in `pyproject.toml` so clones reproduce
exactly. To work on it from the sibling checkout, overlay an editable install (it
sticks as long as the re-sync that would revert it is skipped):

```bash
export UV_NO_SYNC=1                 # for this shell; required so the overlay sticks
uv pip install -e ../psyexp-core    # one time
uv run heat-task                    # uses your local core, edits are live
```

After changing *other* dependencies you'll need a manual `uv sync` (auto-sync is
off) — that re-clobbers psyexp-core, so re-run the editable install above.

The task reads a TOML run file from `conditions/`. Each `[[sequence]]` mirrors one
MMS program column (baseline → ramp-up → hold → ramp-down → trailing baseline);
`time_before_s` is the MMS "Time Before Sequence" lead-in (default 0). Example:

```toml
program_word = "00001111"

[[sequence]]
baseline = 32.0
target_temp = 45.0
time_before_s = 20.0               # lead-in before the first ramp
target_hold_duration_s = 30.0      # hold at target before ramp-down
baseline_duration_s = 30.0         # trailing baseline after ramp-down
```

At launch the task selects the program in MMS, keeps a participant crosshair on screen, and waits
for the experimenter to press the start key in PsychoPy after manual pretest in MMS.
