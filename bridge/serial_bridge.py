#!/usr/bin/env python3
"""
serial_bridge.py
Bridges Godot (TCP localhost:6551) <-> Arduino (Serial).

Usage:
    python3 serial_bridge.py                  # auto-detect Arduino port
    python3 serial_bridge.py /dev/ttyUSB0     # specify port explicitly
    python3 serial_bridge.py COM3             # Windows

Requirements:
    pip install pyserial
"""

import socket
import serial
import serial.tools.list_ports
import threading
import sys
import time

TCP_HOST = "127.0.0.1"
TCP_PORT = 6551
BAUD     = 9600

arduino_ready = False


def find_arduino():
    """Auto-detect the most likely Arduino serial port."""
    ports = serial.tools.list_ports.comports()
    print("[bridge] Available serial ports:")
    for p in sorted(ports, key=lambda x: x.device):
        print(f"         {p.device}  —  {p.description}  [{p.manufacturer}]")
    if not ports:
        print("         (none found)")
    keywords = ("arduino", "ch340", "ch341", "cp210", "usbmodem", "usbserial", "ftdi")
    for p in sorted(ports, key=lambda x: x.device):
        haystack = " ".join([
            p.device or "",
            p.description or "",
            p.manufacturer or "",
        ]).lower()
        if any(k in haystack for k in keywords):
            return p.device
    # fallback: first available port
    if ports:
        return ports[0].device
    return None


def read_from_arduino(ser: serial.Serial):
    """Print every line the Arduino sends (runs in background thread)."""
    while True:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").rstrip()
            if line:
                print(f"  ← Arduino: {line}")
        except Exception:
            break


def handle_client(conn: socket.socket, addr, ser: serial.Serial) -> bool:
    """Forward newline-delimited commands from Godot to Arduino.
    Returns False if the serial port died (caller should reconnect)."""
    global arduino_ready
    print(f"[bridge] Godot connected from {addr}")

    # Drain any data that accumulated in the OS TCP receive buffer
    # while we were waiting for the Arduino bootloader.
    conn.setblocking(False)
    try:
        while conn.recv(4096):
            pass
    except BlockingIOError:
        pass
    conn.setblocking(True)
    print("[bridge] socket queue cleared — ready to forward commands")

    buf = b""
    serial_ok = True
    try:
        while True:
            chunk = conn.recv(256)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                cmd = line.decode("utf-8", errors="ignore").strip()
                if not cmd:
                    continue
                if not arduino_ready:
                    print(f"  ⚠ dropped (Arduino not ready): {cmd}")
                    continue
                print(f"  → Arduino: {cmd}")
                try:
                    ser.write((cmd + "\n").encode("utf-8"))
                    ser.flush()
                    conn.sendall(b"ok\n")
                except serial.SerialException as se:
                    print(f"[bridge] serial error: {se}")
                    serial_ok = False
                    return serial_ok
    except Exception as e:
        print(f"[bridge] network error: {e}")
    finally:
        conn.close()
        print("[bridge] Godot disconnected.")
    return serial_ok


def open_serial(port: str) -> serial.Serial:
    """Open serial port and wait hard for Arduino bootloader to finish."""
    while True:
        try:
            ser = serial.Serial(port, BAUD, timeout=1)
            ser.reset_input_buffer()                      # discard any noise on open
            print("[bridge] Waiting 2.5s for Arduino bootloader …")
            time.sleep(2.5)                               # hard block — bootloader takes ~2s
            ser.reset_input_buffer()                      # discard anything sent during wait
            print("[bridge] Arduino ready.")
            threading.Thread(target=read_from_arduino, args=(ser,), daemon=True).start()
            return ser
        except serial.SerialException as e:
            print(f"[bridge] Waiting for {port} … ({e})")
            time.sleep(2)


def main():
    global arduino_ready
    port = sys.argv[1] if len(sys.argv) > 1 else find_arduino()

    if not port:
        print("ERROR: No serial port found.")
        print("  Plug in the Arduino, or run:  python3 serial_bridge.py /dev/ttyXXX")
        sys.exit(1)

    print(f"[bridge] Opening {port} @ {BAUD} baud …")
    ser = open_serial(port)
    arduino_ready = True

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((TCP_HOST, TCP_PORT))
    server.listen(1)
    print(f"[bridge] Listening on {TCP_HOST}:{TCP_PORT} — start Godot now.")

    try:
        while True:
            conn, addr = server.accept()
            serial_ok = handle_client(conn, addr, ser)
            if not serial_ok:
                arduino_ready = False
                print(f"[bridge] Serial lost — reconnecting to {port} …")
                try:
                    ser.close()
                except Exception:
                    pass
                ser = open_serial(port)
                arduino_ready = True
    except KeyboardInterrupt:
        print("\n[bridge] Shutting down.")
    finally:
        server.close()
        ser.close()


if __name__ == "__main__":
    main()
