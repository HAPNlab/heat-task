# MMS networking & status polling

How the task talks to the Medoc Main Station (MMS / TSA 2) over TCP, and the
design choices that keep the status poll loop responsive. Read this before
touching `medoc/transport.py`, `medoc/client.py`, or the `StatusPoller` in
`task/status.py`.

## The protocol

MMS external control is a **small-message, synchronous request/response**
protocol over TCP (default port `20121`, `MedocTransport.DEFAULT_PORT`). Both
directions are length-prefixed frames, little-endian:

- **Command:** `[uint32 length] [uint32 timestamp] [uint8 command] [uint32 parameter, optional]`
- **Response:** `[uint32 length] [uint32 timestamp] [uint8 command] …` (see
  `RESPONSE_FORMAT` in `medoc/protocol.py`)

where `length` counts every byte after the length field itself. Encoding and
decoding live in `medoc/protocol.py`; the socket and framing live in
`medoc/transport.py` (`recv_frame` reads the 4-byte length, then exactly that
many body bytes).

### One response per connection

The MMS serves **exactly one response per TCP connection and then closes it.**
There is no persistent-session mode. Every command therefore opens its own
short-lived socket:

- One-off commands (`select_test`, `start`) go through
  `MedocClient.connect(...)`, which connects, sends, reads one reply, and closes.
- The `StatusPoller` (a daemon thread in `task/status.py`) does the same on a
  loop: connect → `STATUS` → read reply → close → sleep → repeat. Each sample
  feeds the temperature trace and the live console view.

Reusing a socket across polls does **not** work here — the second send lands on
a socket the MMS has already closed, which surfaces as a spurious failure. The
connect-per-poll design is deliberate, not an oversight. On a healthy LAN a
connect costs a few milliseconds, well within the ~100 Hz poll budget.

## Latency: Nagle and delayed ACKs

A small request/response protocol over TCP is the classic trigger for the
**Nagle ↔ delayed-ACK** interaction. Nagle's algorithm (on by default) holds
small outgoing segments until the peer ACKs outstanding data; the peer's
delayed-ACK optimization holds ACKs for up to ~40–200 ms hoping to piggyback
them. The two can stall each other until the delayed-ACK timer fires, producing
periodic 40–200 ms hitches with no error.

This isn't hypothetical for us: a `tcpdump` capture of 400 connect-per-poll
status exchanges **strongly suggests Nagle-like behavior on the MMS.** The MMS
sends each reply as two TCP payloads — a 4-byte length prefix (bytes
`13 00 00 00`, i.e. a 19-byte body to follow), then the 19-byte body — and in
399/400 connections the body isn't seen until *after* our machine ACKs the
prefix. That's exactly what you'd expect if the MMS wrote two tiny chunks and its
TCP stack held the second until the first was acknowledged. A packet capture
can't read the peer's socket options directly, so this is strong behavioral
evidence rather than proof, but the pattern is unambiguous.

We disable Nagle on our own side — `MedocTransport.connect` sets it on every
socket it opens:

```python
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
```

This is good defensive practice but isn't the main thing saving us here: we send
only one small payload per fresh connection, which Nagle generally wouldn't hold
anyway. `TCP_NODELAY` also can't touch the *peer's* Nagle, and `TCP_QUICKACK`
(the receive-side mitigation) is Linux-only and non-persistent. What actually
keeps the MMS's split reply from stalling is our receiver ACKing the prefix
quickly — in this capture, median ~43 µs (worst case ~107 µs), after which the
body followed within ~8 µs. Full command→reply ran median ~0.85 ms (mean ~1.0 ms,
p95 ~2.0 ms, max ~6.3 ms), with nothing anywhere near the 30–220 ms delayed-ACK
band. (For reference, this run polled at ~66 reads/s — median spacing ~15 ms —
below the `POLL_INTERVAL_S` ~100 Hz cap once per-poll connect cost is included.)

So the stall is **latent, not eliminated**. The current run is fine only because
our receiving TCP stack chose to ACK the prefix quickly. If a different host, OS,
network path, or load caused that ACK to be delayed ~40 ms — which delayed-ACK
heuristics can do — the same two-piece response pattern would turn into visible
40–200 ms hitches with no error (see §"If spikes persist"). To re-check on a
given host, capture `tcp port 20121` and confirm the body segment still departs
right after our prefix ACK rather than racing ahead of it.

> **Measurement setup (2026-06-25).** These numbers describe one specific
> configuration and shouldn't be treated as universal. MMS Arbel v7.0.0.25
> (32-bit x86) running on virtualized Windows 11 25H2 under VMware Fusion
> (Professional 25H2u1) on a 2024 Mac mini (Apple M4 Pro) running macOS Tahoe
> 26.5.1; the capture and probe ran from the macOS host against the guest over
> the VM's bridged network. A virtual NIC and host↔guest bridging have their own
> buffering and ACK timing, so the prefix-ACK speed that keeps the MMS's Nagle
> benign here may not hold on physical hardware, a different hypervisor, or a
> real LAN — which is the whole reason the risk above is "latent, not
> eliminated." Re-measure on the actual deployment target.

## Failure handling and backoff

Because each poll is an independent connect, failures are handled per-poll
rather than by tracking socket state (`StatusPoller._run`):

- **Connect failure** (host down, connect timeout): the poller emits a
  `NetEvent` describing the cause and how long the connect took, then waits using
  **bounded exponential backoff** — `RECONNECT_BACKOFF_S` doubling up to
  `RECONNECT_BACKOFF_MAX_S` — so a down MMS isn't hammered. A successful connect
  resets the backoff.
- **Empty / undecodable reply or send error**: the poll yields `response is
  None`, the poller emits a `NetEvent`, and the loop continues to the next poll
  immediately. The socket is already closed (the MMS closes after every
  response), so there is no stream to resynchronise.

Every `NetEvent` carries `since_last_sample_s`, the time since the last good sample, so a
sequence of failures shows how long data has actually been stalled. Successful
polls record `StatusSample.rtt_ms`, the measured round-trip time.

## Tuning knobs (`config.py`)

| Constant | Value | Why |
|---|---|---|
| `POLL_INTERVAL_S` | `0.01` (~100 Hz) | Caps poll rate. Polling with no gap hammers MMS at the raw link rate, which provokes dropped/late responses and floods the trace with near-duplicate rows. 100 Hz is well above the thermode's real update rate. |
| `POLL_RECV_TIMEOUT_S` | `0.5` | Receive timeout for the **poller's** socket. A status query returns in ms on a healthy link, so this bounds how long one stalled poll can block before it's reported and retried. |
| `RECV_TIMEOUT_S` | `2.0` | Receive timeout for **one-off** commands (`select_test`, `start`), which can legitimately take longer; kept generous. |
| `CONNECT_TIMEOUT_S` | `5.0` | TCP connect timeout. |
| `RECONNECT_BACKOFF_S` | `0.05` | Initial wait after a connect failure before retrying. |
| `RECONNECT_BACKOFF_MAX_S` | `1.0` | Ceiling for the exponential backoff. |

## Live console diagnostics (`console.py`)

`SequenceLiveView` surfaces link health so a stall is obvious and distinguishable
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
  `_FREEZE_AFTER_S` (0.5 s), counting up live.

## If spikes persist

The measures above address the **software** causes. If you still see latency
peaks or freezes, the remaining suspect is the **physical link** — packet loss
triggering TCP retransmission timeouts (which start ~200 ms–1 s and back off
exponentially). No code change fixes that. Check:

- MMS on a **wired** connection, not Wi-Fi.
- A clean switch / direct cable, no congested or flaky hops.
- Use the live `latency peak` readout to localise: low peaks but still freezing
  points away from the app and toward the network or MMS itself.
