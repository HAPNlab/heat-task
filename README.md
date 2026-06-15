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

> On Apple Silicon, psychtoolbox is installed manually (see `pyproject.toml`), and
> `uv run` would otherwise remove it. Launch with `uv run --no-sync heat-task`
> (or `export UV_NO_SYNC=1`) to keep the manual install.

The task reads a TOML run file from `conditions/`. Example:

```toml
program_word = "00001111"

[[trial]]
baseline = 32.0
target_temp = 45.0
```

At launch the task selects the program in MMS, keeps a participant crosshair on screen, and waits
for the experimenter to press the start key in PsychoPy after manual pretest in MMS.
