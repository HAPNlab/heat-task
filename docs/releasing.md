# Release Guide

This document describes how releases of `heat-task` are versioned, verified, and published.

Because this task drives a thermode and collects real participant data, **a stable release is a
promise that the task has been verified against MMS on production hardware**. Anything not fully
verified is published only as a pre-release (see [Pre-releases](#pre-releases)).

## Versioning (SemVer)

We follow [Semantic Versioning 2.0.0](https://semver.org/): `MAJOR.MINOR.PATCH`.

- **MAJOR** — changes that break compatibility or alter the experimental design in a way that makes
  data **not comparable** to prior versions (e.g. changed phase-detection criteria, the recorded
  schema, or the rating scale).
- **MINOR** — backward-compatible functionality (new tooling, optional flags, added outputs) that
  does not change the stimulus/timing contract of an existing run.
- **PATCH** — backward-compatible bug fixes and documentation that do not change task behavior.

> **Data-comparability rule of thumb:** if data collected with the new version cannot be pooled with
> data from the previous version without caveat, it is at least a MINOR bump and usually a MAJOR
> one. When in doubt, bump higher.

The version lives in two places that must stay in sync:

- `pyproject.toml` → `[project].version`
- `CHANGELOG.md` → the top heading

The git tag is the same version prefixed with `v` (e.g. `v1.2.3`). The
[release workflow](../.github/workflows/release.yml) enforces this automatically: it fails the
release if `pyproject.toml`'s version does not match the tag, if `CHANGELOG.md` has no heading for
that version, or if `uv.lock` is out of sync with `pyproject.toml`.

## Pre-releases

A version is only released **stable** once it has been thoroughly verified (see
[Verification](#verification-required-before-a-stable-release)). Until then, publish a pre-release
using a SemVer pre-release suffix:

| Suffix | Meaning |
|--------|---------|
| `-alpha.N` | Early; functionality may be incomplete. Not verified against hardware. |
| `-beta.N`  | Feature-complete, undergoing testing. Partially verified. |
| `-rc.N`    | Release candidate. Verification in progress / final sign-off pending. |

Examples: `v1.2.0-alpha.1`, `v1.2.0-beta.2`, `v1.2.0-rc.1`.

The [release workflow](../.github/workflows/release.yml) automatically marks any tag carrying an
`-alpha`, `-beta`, or `-rc` suffix as a **GitHub pre-release**. Tags without a suffix are published
as full releases. Pre-release ordering follows SemVer precedence:
`1.2.0-alpha.1 < 1.2.0-beta.1 < 1.2.0-rc.1 < 1.2.0`.

## Verification required before a stable release

Do **not** drop the pre-release suffix until all of the following hold.

1. **Automated tests pass:**
   ```bash
   uv run pytest
   ```
2. **End-to-end run against MMS.** Run a full session against the thermode (or a Medoc MMS test
   bench) and confirm:
   - The program selects, pretest is accepted, and `START` begins PsychoPy and the thermode
     together.
   - Each sequence's ramp-up, hold, and ramp-down are detected and the **READY** cue and rating
     slider appear at the right phases.
   - Quitting (Escape / Ctrl-C) and a clean finish both leave the thermode stopped (`ABORT` /
     `STOP`).
3. **Recorded data validated.** Inspect a full run's `behavioral_*.csv` and
   `temperature_trace_*.csv` and confirm phase onset times, ratings, and the temperature stream are
   correct and internally consistent. Run with `--save-net-events` and confirm there are no
   unexpected poll failures (see [MMS Networking](mms-networking.md)).
4. **Run file matches the MMS program.** Confirm the `conditions/*.toml` mirrors the MMS program in
   use (see [MMS Program Parameters](mms-program-parameters.md)) so the tracker's priming hints
   line up with the real schedule.

If any of the above is incomplete, keep the appropriate pre-release suffix.

## Cutting a release

1. **Verify** per the checklist above (or decide on a pre-release suffix).
2. **Update `CHANGELOG.md`**: move the entries under a new heading whose version matches the tag
   (without the leading `v`). The format follows
   [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the release workflow extracts this
   section as the release notes. Commit this first — `make release` requires a clean tree and a
   matching `CHANGELOG.md` heading.
3. **Cut the release with the Makefile.** It bumps `pyproject.toml`, re-locks `uv.lock`, commits,
   and creates the annotated tag — running the same guards as CI first (valid SemVer, clean tree,
   tag not already present, `CHANGELOG.md` heading exists):
   ```bash
   make release TO=1.2.3        # or TO=1.2.3-rc.1 for a pre-release
   git push --follow-tags
   ```
   Convenience wrappers compute the next version for you: `make bump-patch`, `make bump-minor`,
   `make bump-major`. To undo a tag before it is pushed (or after, if no GitHub release points at
   it): `make delete-tag TAG=v1.2.3`.
4. The [release workflow](../.github/workflows/release.yml) creates a **draft** GitHub Release with
   notes pulled from `CHANGELOG.md` and the source archives attached, and marks it as a pre-release
   if the tag has an `-alpha`/`-beta`/`-rc` suffix.
5. **Review the draft** release on GitHub and publish it.

> Prefer the Makefile over bumping and tagging by hand — it keeps `pyproject.toml`, `uv.lock`, and
> the tag in lock-step and fails locally on the same checks the release workflow enforces.

> The release is created as a **draft** so a human reviews it before it goes live — the final gate on
> the verification promise above.
