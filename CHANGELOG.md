# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

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
