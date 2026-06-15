# MMS networking & status polling

How the task talks to the Medoc Main Station (MMS / TSA 2) over TCP, and the
latency pitfalls that were fixed. Read this before touching `medoc/transport.py`,
`medoc/client.py`, or the `StatusPoller` in `trial.py`.

## The protocol

MMS external control is a **small-message, synchronous request/response**
protocol over TCP (default port 20121):

- We send a short command (e.g. `STATUS`), then read a length-prefixed reply
  (4-byte little-endian length + body). See `medoc/protocol.py` and
  `medoc/transport.py`.
- The `StatusPoller` (a daemon thread in `trial.py`) holds **one long-lived
  connection** and polls `STATUS` in a tight loop. Each sample feeds the
  temperature trace and the live console view.
- One-off commands (`select_test`, `start`) use their own short-lived
  connections via `MedocClient.connect(...)`.

This shape — tiny payloads, one in flight at a time, on a persistent socket — is
exactly where naive TCP usage produces mysterious latency. Two distinct
failure modes were observed and fixed.

## Problem 1: periodic 40–200 ms spikes (Nagle ↔ delayed-ACK)

**Symptom:** the poll loop, normally sub-millisecond, intermittently hitched by
tens to a couple hundred milliseconds, with no error.

**Cause:** Nagle's algorithm (on by default) coalesces small TCP segments and
holds them until the peer ACKs outstanding data. The peer's **delayed-ACK**
optimization holds ACKs for up to ~40–200 ms hoping to piggyback them. In a
small request/response protocol the two can deadlock until the delayed-ACK timer
fires — producing periodic stalls.

**Fix:** disable Nagle on the socket (`medoc/transport.py`):

```python
self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
```

This is standard for interactive request/response protocols. Note it only
disables Nagle on *our* side; if the peer batches its own segments, a residual
delayed-ACK stall isn't something we control cross-platform (`TCP_QUICKACK` is
Linux-only and non-persistent).

## Problem 2: multi-second freezes (stream desync on timeout)

**Symptom:** occasional freezes lasting **seconds** — `TCP_NODELAY` did not help.

**Cause:** a framing-desync hazard in the long-lived poller socket. If a `recv`
timed out **mid-frame** — after reading the 4-byte length but before the body —
the partial bytes were discarded and the socket was **reused**. The poller only
reconnected on an *exception*; an empty/`None` response just looped and sent
another request on a now-desynced stream. From then on every read was misframed,
`decode_response` raised `ValueError` → `None`, and the poller spun on garbage
until an actual socket error finally forced a reconnect. One mid-frame timeout
cascaded into a long freeze.

**Fix (`trial.py`, `StatusPoller._run`):** treat **any** failed/empty/undecodable
response as a reason to drop the socket and reconnect, resynchronising the
stream instead of reusing it:

```python
if response is None:
    client.close()
    client = None
    continue
```

## Tuning knobs (`config.py`)

| Constant | Value | Why |
|---|---|---|
| `POLL_INTERVAL_S` | `0.01` (~100 Hz) | Caps poll rate. The previous `0.0` hammered MMS at the raw link rate, which provoked dropped/late responses and flooded the trace with near-duplicate rows. 100 Hz is well above the thermode's real update rate. |
| `POLL_RECV_TIMEOUT_S` | `0.5` | Receive timeout for the **poller's** socket. A status query returns in ms on a healthy link, so a stall past this bounds the freeze before we resync. |
| `RECV_TIMEOUT_S` | `2.0` | Receive timeout for **one-off** commands (`select_test`, `start`), which can legitimately take longer; kept generous. |
| `CONNECT_TIMEOUT_S` | `5.0` | TCP connect timeout. |

## Live console diagnostics (`console.py`)

`TrialLiveView` surfaces link health so a stall is obvious and distinguishable
from an app hang:

- **`● Running`** — a blinking heartbeat driven by the render loop (via
  `view.tick()` every frame), *not* by sample arrival. It keeps pulsing as long
  as the app loop runs, so "app alive but data stalled" looks different from
  "app hung."
- **`latency … avg · … peak`** — the **true MMS round-trip time** measured in the
  poller thread (`StatusSample.rtt_ms`), averaged over a trailing window with the
  recent peak surfaced so spikes stay visible for a moment. Colour-coded
  green/yellow/red by severity.
- **`(frozen Xs)`** — appears when no fresh sample has arrived for
  `_FREEZE_AFTER_S`, counting up live.

## If spikes persist

The fixes above address the **software** causes. If you still see latency peaks
or freezes after this, the remaining suspect is the **physical link** — packet
loss triggering TCP retransmission timeouts (which start ~200 ms–1 s and back off
exponentially). No code change fixes that. Check:

- MMS on a **wired** connection, not Wi-Fi.
- A clean switch / direct cable, no congested or flaky hops.
- Use the live `latency peak` readout to localise: low peaks but still freezing
  points away from the app and toward the network or MMS itself.
