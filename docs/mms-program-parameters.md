# MMS program parameters

How a Medoc MMS **program** is structured, what each parameter means, and how it
maps onto a heat-task run file (`conditions/*.toml`). Read this before editing a
run file or building a matching program in MMS.

The task does **not** read the program from MMS — it only sends `SELECT_TEST` +
`START` and then *observes* the thermode's temperature stream, inferring phases
from the curve (see `mms-networking.md` and the state diagram in `config.py`).
So the run file must **mirror** the MMS program: if the two disagree, the task
still records, but its priming hints (when it expects each ramp) drift off the
real schedule. Treat the MMS program as the source of truth and keep the TOML in
sync with it.

## Where the parameters live

In MMS: **TEST → PROGRAMS**. A program is a table — **one column per
*sequence***, with parameters as rows. The example below is the program
`SingleProbe_46-48_Run1` (probe `TSA`), which `conditions/example.toml` mirrors.

> **Terminology.** A column is a **sequence** (one baseline → ramp → hold → ramp
> → baseline cycle). MMS's own **"Number of Trials"** row is a *repeat count
> within* a sequence — a separate concept. heat-task uses "sequence" for the
> column and never uses "trial" for it; the run file's tables are `[[sequence]]`.

## Program-level parameters

These apply to the whole program (the header row in the editor):

| MMS field | Example | Meaning | heat-task |
|---|---|---|---|
| **Program Name** | `SingleProbe_46-48_Run1` | Identifier selected by `SELECT_TEST`. | Chosen via the program word (`program_word`), not the name string. |
| **Probe** | `TSA` | Which thermode/probe the program drives. | Not modelled (hardware setup). |
| **Randomize sequences** | off | Shuffle sequence order at run time. | Not supported — keep **off** so the recorded order matches the TOML order. |
| **Manually define the next sequence** | off | Operator advances sequences by hand. | Not supported — keep **off** (the task expects auto progression). |
| **Start Test / End Test** (TTL, Sound) | off | External trigger / tone at test start/end. | Not used; the task fires `START` itself on the start key. |
| **Time Between Trials** | `End to Onset` | How the inter-stimulus gap (ISI) is measured — here from the **end** of one sequence to the **onset** of the next. | Determines that `baseline_duration_s` is a clean post-ramp-down gap (see timeline below). |

## Per-sequence parameters

One column per sequence. Values shown are for the six sequences of the example
program (`46, 48, 48, 46, 46, 48` destinations; everything else identical):

| MMS row | Example | Meaning | heat-task field |
|---|---|---|---|
| **Sequence** | `1 … 6` | Column index / order. | Position of the `[[sequence]]` table; reported as `sequence_n`. |
| **Baseline (°C)** | `35` | Resting temperature held before the ramp and returned to after. | `baseline` |
| **Time Before Sequence (sec)** | `20, 0, 0, 0, 0, 0` | Lead-in held at baseline before this sequence's ramp begins. Typically non-zero only on sequence 1 (the initial delay). | `time_before_s` (default `0.0`) |
| **Trigger** | `Auto` | How the ramp is triggered. `Auto` = on schedule. | Assumes `Auto`; the task does not gate ramps. |
| **Destination Temperature (°C)** | `46 / 48` | Target temperature of the ramp-up (the painful peak). | `target_temp` (must be `> baseline`) |
| **Destination Rate (°C/sec)** | `4.5` | Ramp-**up** speed toward the destination. | Not a field, but shapes the curve the detector watches (see *Detection* below). |
| **Destination Criterion** | `Temperature` | What ends the ramp-up — reaching the temperature (vs. a time/criterion). | Assumes temperature-criterion (the tracker keys off `target_temp`). |
| **Duration Time (sec)** | `30` | How long the destination temperature is **held** before returning. | `target_hold_duration_s` |
| **Return Option** | `Baseline` | Where the sequence returns after the hold — back to baseline. | Assumes `Baseline` (the tracker's "complete" = back at baseline). |
| **Return Rate (°C/sec)** | `3` | Ramp-**down** speed back to baseline. | Not a field; shapes the ramp-down curve (see *Detection*). |
| **Number of Trials** | `1` | Repeats of this sequence's stimulus within the column. | Only `1` is modelled — one ramp/hold per `[[sequence]]`. |
| **Enable Pain Rating** | off | Whether MMS collects a rating. | The task owns rating via PsychoPy (`RatingController`), independent of MMS. |
| **First pain rating (sec)** | `0` | MMS rating onset. | n/a — see above. |
| **Pain rating interval (sec)** | `0` | MMS repeat-rating cadence. | n/a — see above. |
| **Waiting time for response (sec)** | `10` | MMS rating timeout. | The task's own timeout is `RATING_TIMEOUT_S` in `config.py`. |
| **Randomize with Next** | off | Shuffle this sequence with the following one. | Not supported — keep **off**. |
| **ISI Min / Max (sec)** | `30 / 30` | Inter-stimulus interval — the baseline gap after the return, before the next sequence's onset (per *Time Between Trials = End to Onset*). Equal min/max = fixed; unequal = random in range. | `baseline_duration_s`. Use **equal** min/max; the task expects a fixed, known baseline length. |
| **Standard / Temperature Events** | — | Marker/event outputs. | Not modelled. |

## Timeline of one sequence

How the parameters compose, with the example values (`time_before_s` = 20 on
sequence 1 only; rate 4.5 up / 3 down; 30 s hold; 30 s ISI):

```
                  Destination Temperature (46–48 °C)
                   ┌──────── Duration Time ────────┐
                   │           (30 s hold)         │
   Dest. Rate ───▶ │                               │ ◀─── Return Rate
    (4.5 °C/s)   ╱ │                               │ ╲    (3 °C/s)
              ╱    │                               │   ╲
   ──────────╱     │                               │     ╲──────────────
   Baseline (35 °C)                                       Baseline
   │◀ Time Before ▶│                               │◀──── ISI ────▶│
   │   Sequence    │                                  (baseline_     (next
   │   (20 s, seq 1)                                  duration_s,     sequence
   onset                                              30 s)           onset)
```

Each sequence **owns its trailing ISI**: the run file consumes
`baseline_duration_s` at the *end* of the sequence (after the return), not as a
lead-in to the next one. The final sequence is no exception — the task waits out
its ISI before the closing screen. See the `task/sequence.py` module docstring.

## How the example program maps to the run file

`conditions/example.toml` (excerpt) mirrors the screenshot one-to-one:

```toml
program_word = "00001111"

[[sequence]]
baseline = 35.0                    # Baseline (°C)
target_temp = 46.0                 # Destination Temperature (°C)
time_before_s = 20.0               # Time Before Sequence (sec) — seq 1 only
target_hold_duration_s = 30.0      # Duration Time (sec)
baseline_duration_s = 30.0         # ISI Min/Max (sec)
# … five more [[sequence]] tables: 48, 48, 46, 46, 48 destinations …
```

`program_word` is an 8-bit string that encodes which MMS program to `SELECT_TEST`
(decoded to `program_id`); it is not a per-sequence parameter.

## Detection: rates and tolerances

The task infers each phase from the **smoothed temperature curve**, so the MMS
**Destination Rate** / **Return Rate** matter even though they aren't run-file
fields: they set how fast the curve moves through the detector's thresholds
(`RAMP_START_DELTA`, `TARGET_TOLERANCE`, `RAMP_DOWN_DELTA`, `BASELINE_TOLERANCE`
in `config.py`). Very slow rates (shallow slopes) can fall below
`MIN_SLOPE_PER_SAMPLE` and delay or miss a transition; the example's 4.5 / 3
°C·s⁻¹ are comfortably steep. Near each scheduled transition the tracker
*primes* to tighter thresholds (`PRIME_WINDOW_S`), which is why the run file's
durations must track the MMS program — they tell the tracker *when* to expect the
ramp it's watching for.
