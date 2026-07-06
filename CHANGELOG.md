# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
