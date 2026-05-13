#!/usr/bin/env python3
"""
medoc_run_and_poll.py

Run a Medoc program and poll status (if status command is known).

IMPORTANT:
- This assumes your MMS build accepts raw byte commands over TCP.
- If your build needs a framed protocol, you'll still get logs, but command may be ignored.
"""

import argparse
import csv
import socket
import time
from datetime import datetime
from typing import Optional


def parse_u8(value: str) -> int:
    """
    Accept:
      - binary string: '00001111'
      - hex string:    '0x0f'
      - decimal:       '15'
    Returns int 0..255
    """
    v = value.strip().lower()
    if set(v) <= {"0", "1"} and len(v) <= 8:
        n = int(v, 2)
    elif v.startswith("0x"):
        n = int(v, 16)
    else:
        n = int(v, 10)
    if not (0 <= n <= 255):
        raise ValueError(f"Value out of u8 range: {value}")
    return n


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def hex_bytes(b: bytes) -> str:
    return b.hex(" ") if b else ""


def recv_nonblocking(sock: socket.socket, timeout_s: float = 0.15) -> bytes:
    """
    Read whatever is immediately available (up to timeout).
    """
    sock.settimeout(timeout_s)
    chunks = []
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
            # If data is flowing, keep reading until timeout
            sock.settimeout(0.02)
        except socket.timeout:
            break
    return b"".join(chunks)


def log_event(direction: str, payload: bytes, writer: Optional[csv.writer] = None) -> None:
    line = f"{ts()} {direction} {hex_bytes(payload)}"
    print(line)
    if writer is not None:
        writer.writerow([ts(), direction, payload.hex()])


def send_cmd(sock: socket.socket, payload: bytes, writer: Optional[csv.writer] = None) -> bytes:
    log_event("TX", payload, writer)
    sock.sendall(payload)
    rx = recv_nonblocking(sock)
    if rx:
        log_event("RX", rx, writer)
    return rx


def main() -> None:
    p = argparse.ArgumentParser(description="Run Medoc program and poll status")
    p.add_argument("--host", default="172.16.56.128", help="Medoc host IP")
    p.add_argument("--port", type=int, default=20121, help="Medoc TCP port")
    p.add_argument("--connect-timeout", type=float, default=3.0)

    # Commands (defaults based on your screenshot)
    p.add_argument("--select-cmd", default="00000001", help="Select Test Program command")
    p.add_argument("--start-cmd", default="00000010", help="Start command")
    p.add_argument("--stop-cmd", default="00000101", help="Stop command")
    p.add_argument("--program", default="00001111", help="Program 8-bit word")

    # Behavior
    p.add_argument("--auto-start", action="store_true", default=True,
                   help="If set, do NOT send Start after Select (default true)")
    p.add_argument("--no-auto-start", dest="auto_start", action="store_false",
                   help="Send Start command after Select")
    p.add_argument("--status-cmd", default=None,
                   help="Status command u8 (e.g., 00010000 or 0x10). If omitted, listen-only.")
    p.add_argument("--poll-hz", type=float, default=5.0, help="Status poll frequency")
    p.add_argument("--duration", type=float, default=30.0, help="Run duration seconds")
    p.add_argument("--send-stop-on-exit", action="store_true", default=True)
    p.add_argument("--no-stop-on-exit", dest="send_stop_on_exit", action="store_false")
    p.add_argument("--log-csv", default=None, help="Optional CSV log path")

    args = p.parse_args()

    select_cmd = parse_u8(args.select_cmd)
    start_cmd = parse_u8(args.start_cmd)
    stop_cmd = parse_u8(args.stop_cmd)
    program_id = parse_u8(args.program)
    status_cmd = parse_u8(args.status_cmd) if args.status_cmd is not None else None

    csv_file = None
    writer = None
    if args.log_csv:
        csv_file = open(args.log_csv, "w", newline="")
        writer = csv.writer(csv_file)
        writer.writerow(["timestamp", "direction", "hex"])

    try:
        print(f"{ts()} Connecting to {args.host}:{args.port} ...")
        with socket.create_connection((args.host, args.port), timeout=args.connect_timeout) as sock:
            print(f"{ts()} Connected.")

            # 1) Select program: opcode + operand
            send_cmd(sock, bytes([select_cmd, program_id]), writer)

            # 2) If auto-start is off, send Start
            if not args.auto_start:
                send_cmd(sock, bytes([start_cmd]), writer)

            # 3) Poll loop
            poll_interval = 1.0 / max(args.poll_hz, 0.1)
            t_end = time.monotonic() + max(args.duration, 0.0)
            next_poll = time.monotonic()

            while time.monotonic() < t_end:
                now = time.monotonic()

                if status_cmd is not None and now >= next_poll:
                    send_cmd(sock, bytes([status_cmd]), writer)
                    next_poll += poll_interval

                # Also listen for unsolicited data
                rx = recv_nonblocking(sock, timeout_s=0.05)
                if rx:
                    log_event("RX", rx, writer)

                time.sleep(0.01)

            if args.send_stop_on_exit:
                try:
                    send_cmd(sock, bytes([stop_cmd]), writer)
                except Exception as e:
                    print(f"{ts()} WARN: failed to send Stop: {e}")

        print(f"{ts()} Done.")

    finally:
        if csv_file:
            csv_file.close()


if __name__ == "__main__":
    main()
