#!/usr/bin/env python3
import argparse
import socket
import time
import sys


def probe(host: str, port: int, timeout: float, hold: float, send_hex: str | None, read_timeout: float):
    t0 = time.perf_counter()
    s = socket.create_connection((host, port), timeout=timeout)
    connect_ms = (time.perf_counter() - t0) * 1000

    print(f"✅ Connected to {host}:{port} in {connect_ms:.1f} ms")
    s.settimeout(read_timeout)

    if send_hex:
        payload = bytes.fromhex(send_hex.replace(" ", ""))
        print(f"→ Sending {len(payload)} bytes: {payload.hex(' ')}")
        s.sendall(payload)

        try:
            data = s.recv(4096)
            if data:
                print(f"← Received {len(data)} bytes: {data.hex(' ')}")
            else:
                print("← Remote closed connection (no data)")
        except socket.timeout:
            print(f"⏱ No response within {read_timeout:.1f}s (this can be normal)")

    # Hold the connection open briefly to detect immediate server-side closes
    end_time = time.time() + hold
    while time.time() < end_time:
        try:
            b = s.recv(1, socket.MSG_PEEK)
            if b == b"":
                print("⚠️ Connection was closed by remote side during hold period")
                s.close()
                return False
        except BlockingIOError:
            pass
        except socket.timeout:
            pass
        except Exception:
            # Some platforms may not like MSG_PEEK behavior here; ignore
            pass
        time.sleep(0.1)

    s.close()
    print("✅ Connection test complete")
    return True


def main():
    parser = argparse.ArgumentParser(description="TCP connectivity probe for Medoc/MMS or proxy")
    parser.add_argument("--host", required=True, help="Target host/IP (e.g., 127.0.0.1 or VM IP)")
    parser.add_argument("--port", required=True, type=int, help="Target TCP port")
    parser.add_argument("--tries", type=int, default=3, help="Number of attempts")
    parser.add_argument("--timeout", type=float, default=3.0, help="Connect timeout seconds")
    parser.add_argument("--hold", type=float, default=1.0, help="How long to keep connection open")
    parser.add_argument("--read-timeout", type=float, default=1.0, help="Read timeout seconds")
    parser.add_argument("--send-hex", default=None, help="Optional hex payload, e.g. '01 02 0A FF'")
    args = parser.parse_args()

    any_success = False
    for i in range(1, args.tries + 1):
        print(f"\n--- Attempt {i}/{args.tries} ---")
        try:
            ok = probe(
                host=args.host,
                port=args.port,
                timeout=args.timeout,
                hold=args.hold,
                send_hex=args.send_hex,
                read_timeout=args.read_timeout,
            )
            any_success = any_success or ok
        except Exception as e:
            print(f"❌ Failed: {type(e).__name__}: {e}")
        time.sleep(0.3)

    sys.exit(0 if any_success else 1)


if __name__ == "__main__":
    main()
