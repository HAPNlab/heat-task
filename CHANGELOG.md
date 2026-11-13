# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- The pain-rating slider now shows a tick mark at each of its 11 integer stops
  (0–10).
- The cursor is locked inside the task window while it is open, so the
  participant's trackball can't move it onto another screen or click anything
  outside the task. `SLIDER_GAIN` in `config.py` sets the slider's speed.
- The task sends the MMS pretest itself, since the locked mouse can't click
  Pre-test in MMS. The operator presses `P` for the pretest; once MMS reports
  the test running with the thermode at the run's first baseline, `0` starts the
  run. A rejected
  pretest, or one that runs past `PRETEST_TIMEOUT_S` (20 s, then `ABORT`),
  stops the task before the run starts.

### Changed

- The slider follows the trackball's movement instead of the cursor's
  position, and stops at each end. Rolling back after pushing past an end now
  moves the marker straight away.

### Fixed

- The phase tracker took the thermode settling after its overshoot (~0.25 °C
  above target, 2–4 s into the hold) for a ramp-down, so the rating appeared
  mid-hold. A small upward wobble then marked the sequence complete, still at
  target. Now a ramp only counts once the temperature is 0.75 °C clear of the
  plateau it left *and* moving at 1 °C/s or faster for 0.1 s. Overshoot,
  undershoot and sensor jitter stay well inside those limits: in a recorded
  run, holds never dipped more than 0.1 °C below target or fell faster than
  0.4 °C/s. Smoothing, slope and debounce are now measured in seconds, not
  polls, and the smoothed temperature is a rolling median, so one or two bad
  readings can't trip a transition.
- If a ramp turns back before reaching the target, the tracker goes to
  ramp-down and the trial still gets its rating, instead of waiting forever for
  a hold.

### Removed

- The tracker no longer switches to looser thresholds ("priming") ahead of a
  scheduled transition. Those thresholds stayed on for the whole hold, which
  is what let the overshoot through. `PRIME_WINDOW_S` and the `PRIMED_*`
  constants are gone.

### Breaking

- `temperature_trace_*.csv`: `rolling_mean_temperature` →
  `rolling_median_temperature`.
- Tracker constants in `config.py` (and `study_params` in the manifest):
  `SMOOTHING_WINDOW`, `TREND_WINDOW`, `CONSECUTIVE_SAMPLES` and
  `MIN_SLOPE_PER_SAMPLE` are replaced by `SMOOTHING_S`, `TREND_S`, `DWELL_S`
  and `MIN_RAMP_RATE`. `RAMP_START_DELTA` and `RAMP_DOWN_DELTA` are now 0.75 °C,
  and `RAMP_DOWN_DELTA` is measured below the target, not below the peak.

## v1.0.0-rc.6

### Added

- `heat-task --poll-interval SECONDS` sets the gap between MMS status polls
  (default unchanged at `0.01`, ~100 Hz). The value is printed at startup and
  recorded in the run manifest.
- `device_return_code` column in `temperature_trace_*.csv`: the MMS return code
  on each status reply, so a safety warning, safety error or device
  communication error during a run is recorded.

### Fixed

- A `START` that MMS never answered was treated as success, so a run could
  carry on after MMS ignored it (e.g. in Safe Mode) while the thermode stayed
  unpowered. The task now checks with `STATUS` that the test is running and
  aborts after 3 s if it is not.
- MMS return codes were decoded bit by bit, so `3` was reported as three errors
  and `0x3000` as a device communication error plus a safety warning. Codes are
  now looked up whole, and `WAITING_MANUAL_OPERATION` (`0x3000`) is recognised.

## v1.0.0-rc.5

### Fixed

- The `SingleProbe_45-46`/`46-47`/`46-48` run files used program words
  `00000001`–`00000110`, which MMS reserves for its external-control commands.
  They now use `00010000`–`00010101` (in file order 45-46 Run1 → 46-48 Run2);
  update the MMS programs to match. Run files with a reserved word (`00000000`–
  `00001110`) are now rejected at load time.

## v1.0.0-rc.4

### Added

- Run files for the `SingleProbe_45-46`, `SingleProbe_46-47`, and
  `SingleProbe_46-48` MMS programs (Run1/Run2 each), generated from the MMS
  `.ats` exports. Each uses a new program word (`00000001`–`00000110`) that must
  be configured to match in MMS.
- Anaconda/Miniconda launch instructions in the usage guide.
- psychtoolbox lab-wheel install instructions for both UV and conda.

### Fixed

- Conda environment on Windows failing with "DLL load failed while importing
  QtCore": `environment.yml` no longer installs `hdf5`/`openblas`/`lapack`,
  whose conda-forge ICU shadowed the Windows system ICU that PyQt6 needs.

### Removed

- The macOS `brew install hdf5 openblas lapack` setup step; the PyPI wheels
  bundle these libraries.

## v1.0.0-rc.3

### Changed

- Bumped `psyexp-core` to `v0.9.0`.
- Consumed the shared `psyexp_core.keyboard` helpers in place of heat's local
  `wait_for_key`/`check_quit`.
- Reworked `__main__` teardown to use a `contextlib.ExitStack`, so each resource
  registers its own cleanup and teardown runs in reverse on every exit.
- Validated the saved last-connection state with a pydantic model instead of
  hand-rolled JSON parsing.

### Fixed

- Restored a remembered screen index of `0`, which was previously dropped by a
  truthiness default when loading the last-connection state.

## v1.0.0-rc.2

### Changed

- Bumped `psyexp-core` to `v0.8.0`

## v1.0.0-rc.1

First release candidate for 1.0.0.

### Added

- Network event logging for MMS diagnostics, with an opt-in CLI flag.
- Screen selection and diagnostics in the setup flow.
- MMS error logging, and use of MMS aborts in cleanup paths.

### Changed

- Switched the Medoc integration to the TCP/IP MMS API.
- Eliminated MMS poll latency spikes and added live-view diagnostics.
- Modeled ramp-and-hold phases as a `StrEnum`.
- Capped `requires-python` to `>=3.11,<3.12`.

### Breaking

- Renamed several output columns for clarity: `baseline` → `baseline_temp`,
  `smoothed_temperature` → `rolling_mean_temperature`, `gap_s` in the net events
  tracker, and additional temp-trace/behavioral columns.
- Renamed the device "testing" mode to "active".
- Run only one MMS program at a time.
