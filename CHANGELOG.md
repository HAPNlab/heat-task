# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

## v0.1.0

Initial release of the ramp-and-hold thermal pain task.

### Added

- Ramp-and-hold PsychoPy task driven by a Medoc MMS thermode.
- Medoc MMS client, protocol, and CLI (`medoc`).
- Ramp/hold detector, recorder, and condition handling.
- Setup wizard and run-directory/recording scaffolding via psyexp-core.
