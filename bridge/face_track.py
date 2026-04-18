"""
face_track.py — Face detection + servo tracking + shared memory output
======================================================================
Extends camera.py (face_check.py) with:
  - Shared memory "robot_frame": live JPEG frame for Godot
  - Shared memory "robot_meta": JSON metadata (face, dist, offsets, servo pos)
  - TCP servo control via bridge on localhost:9000
  - PID-style servo control with deadzone
  - Hotkeys: Q=quit, SPACE=pause/resume, R=reset servos, +/-=adjust gain

    pip install opencv-python
    python face_track.py

Press Q to quit.
"""

import cv2
import json
import os
import socket
import struct
import tempfile
import time
from multiprocessing.shared_memory import SharedMemory

# ── File output paths (read by CameraFeed.gd) ────────────────────────────────
FILE_FRAME = "/tmp/robot_frame.bin"
FILE_META  = "/tmp/robot_meta.json"

# ── Config ────────────────────────────────────────────────────────────────────
CAMERA_INDEX = 0

KNOWN_FACE_WIDTH_CM = 16.0
FOCAL_LENGTH = 600

# Servo config
SERVO_H_CENTER = 80
SERVO_V_CENTER = 60
SERVO_H_MIN    = 40
SERVO_H_MAX    = 120
SERVO_V_MIN    = 30
SERVO_V_MAX    = 90
DEADZONE       = 0.06  # skip if both axes within this (normalized)
SEND_INTERVAL  = 0.15  # seconds between servo commands
SMOOTH         = 0.35  # how fast servo_h/v chase the target (0=frozen, 1=instant)
INVERT_H       = True
INVERT_V       = False

# Bridge
BRIDGE_HOST = "localhost"
BRIDGE_PORT = 9000

# Shared memory layout
# robot_frame: [uint32 counter][uint32 width][uint32 height][RGB pixels 640*480*3]
FRAME_W  = 640
FRAME_H  = 480
FRAME_SHM_SIZE = 12 + FRAME_W * FRAME_H * 3

# robot_meta: 256 bytes, JSON string, null-padded
META_SHM_SIZE = 256

# ── Shared memory setup ───────────────────────────────────────────────────────
def _create_or_attach(name: str, size: int) -> SharedMemory:
    try:
        shm = SharedMemory(name=name, create=True, size=size)
    except FileExistsError:
        shm = SharedMemory(name=name, create=False, size=size)
    return shm

shm_frame = _create_or_attach("robot_frame", FRAME_SHM_SIZE)
shm_meta  = _create_or_attach("robot_meta",  META_SHM_SIZE)
print("[face_track] shared memory ready")

def _write_frame(frame_rgb, counter: int) -> None:
    buf = shm_frame.buf
    struct.pack_into(">III", buf, 0, counter, FRAME_W, FRAME_H)
    flat = frame_rgb.tobytes()
    buf[12:12 + len(flat)] = flat

def _write_meta(meta: dict) -> None:
    raw = json.dumps(meta).encode("utf-8")
    raw = raw[:META_SHM_SIZE - 1].ljust(META_SHM_SIZE, b"\x00")
    shm_meta.buf[:META_SHM_SIZE] = raw

def _write_files(frame_rgb, meta: dict) -> None:
    """Write frame + meta to /tmp atomically so Godot never reads a partial file."""
    try:
        pixels = frame_rgb.tobytes()
        # atomic frame write: write temp then rename (POSIX rename is atomic)
        fd, tmp = tempfile.mkstemp(dir="/tmp", suffix=".bin")
        try:
            os.write(fd, pixels)
        finally:
            os.close(fd)
        os.replace(tmp, FILE_FRAME)
    except Exception:
        pass
    try:
        raw = json.dumps(meta)
        fd, tmp = tempfile.mkstemp(dir="/tmp", suffix=".json")
        try:
            os.write(fd, raw.encode("utf-8"))
        finally:
            os.close(fd)
        os.replace(tmp, FILE_META)
    except Exception:
        pass

# ── Bridge TCP connection ─────────────────────────────────────────────────────
_sock: socket.socket | None = None

def _connect_bridge() -> bool:
    global _sock
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect((BRIDGE_HOST, BRIDGE_PORT))
        s.setblocking(False)
        _sock = s
        return True
    except OSError:
        return False

def _send_servo(axis: str, angle: int) -> None:
    if _sock is None:
        return
    cmd = f"servo:{axis}:{angle}\n"
    try:
        _sock.sendall(cmd.encode("utf-8"))
    except OSError:
        pass

if _connect_bridge():
    print(f"[face_track] bridge connected")
    _send_servo("H", SERVO_H_CENTER)
    _send_servo("V", SERVO_V_CENTER)
    time.sleep(0.1)
    print(f"[face_track] servos initialized to center H={SERVO_H_CENTER} V={SERVO_V_CENTER}")
else:
    print(f"[face_track] bridge not available (continuing without servo output)")

# ── Camera ────────────────────────────────────────────────────────────────────
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)

if not cap.isOpened():
    print(f"[face_track] could not open camera {CAMERA_INDEX}")
    shm_frame.close(); shm_frame.unlink()
    shm_meta.close();  shm_meta.unlink()
    exit(1)

print(f"[face_track] camera open: {FRAME_W}x{FRAME_H}")
print("Hotkeys: Q=quit  SPACE=pause/resume  R=reset servos  +/-=gain")

# ── State ─────────────────────────────────────────────────────────────────────
servo_h           = float(SERVO_H_CENTER)   # smoothed running position (float)
servo_v           = float(SERVO_V_CENTER)
last_sent_h       = SERVO_H_CENTER          # last integer value actually sent
last_sent_v       = SERVO_V_CENTER
face_ever_detected = False
paused            = False
frame_ctr         = 0
last_send         = 0.0

# ── Main loop ─────────────────────────────────────────────────────────────────
try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        cx_frame, cy_frame = w // 2, h // 2

        tracking = False
        face_cx = cx_frame
        face_cy = cy_frame
        distance_cm = 0.0
        off_x = 0.0
        off_y = 0.0

        if not paused:
            gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray  = cv2.equalizeHist(gray)
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
            )

            if len(faces) > 0:
                tracking = True
                face_ever_detected = True
                x, y, bw, bh = max(faces, key=lambda f: f[2] * f[3])

                face_cx = x + bw // 2
                face_cy = y + bh // 2

                distance_cm = (KNOWN_FACE_WIDTH_CM * FOCAL_LENGTH) / bw
                off_x = (face_cx - cx_frame) / (w / 2)
                off_y = (face_cy - cy_frame) / (h / 2)

                # ── Servo control ─────────────────────────────────────────────
                # Smooth servo_h/v toward target every frame (reduces jitter).
                # Target is always anchored to center+offset — no drift possible.
                h_dir = -1 if INVERT_H else 1
                v_dir = -1 if INVERT_V else 1

                target_h = SERVO_H_CENTER + h_dir * off_x * 40
                target_v = SERVO_V_CENTER + v_dir * off_y * 30
                target_h = max(SERVO_H_MIN, min(SERVO_H_MAX, target_h))
                target_v = max(SERVO_V_MIN, min(SERVO_V_MAX, target_v))

                servo_h += (target_h - servo_h) * SMOOTH
                servo_v += (target_v - servo_v) * SMOOTH

                # Send at rate limit, only if face ever seen and changed by 3+ degrees
                now = time.monotonic()
                if face_ever_detected and now - last_send >= SEND_INTERVAL:
                    if not (abs(off_x) < DEADZONE and abs(off_y) < DEADZONE):
                        ih = int(round(servo_h))
                        iv = int(round(servo_v))
                        if abs(ih - last_sent_h) >= 3:
                            _send_servo("H", ih)
                            last_sent_h = ih
                        if abs(iv - last_sent_v) >= 3:
                            _send_servo("V", iv)
                            last_sent_v = iv
                    last_send = now

                # ── Draw face box ─────────────────────────────────────────────
                cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 220, 100), 2)

                l, t = 16, 3
                for px, py, dx, dy in [
                    (x,      y,      1,  1),
                    (x + bw, y,     -1,  1),
                    (x,      y + bh, 1, -1),
                    (x + bw, y + bh,-1, -1),
                ]:
                    cv2.line(frame, (px, py), (px + dx * l, py), (0, 255, 120), t)
                    cv2.line(frame, (px, py), (px, py + dy * l), (0, 255, 120), t)

                cv2.circle(frame, (face_cx, face_cy), 4, (0, 220, 100), -1)
                cv2.line(frame, (cx_frame, cy_frame), (face_cx, face_cy), (0, 180, 80), 1)

                label = f"{distance_cm:.0f} cm"
                cv2.putText(frame, label, (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 100), 2)

                cv2.putText(frame, "FACE DETECTED", (10, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 100), 2)
            else:
                cv2.putText(frame, "no face", (10, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (80, 80, 255), 2)
        else:
            cv2.putText(frame, "PAUSED", (10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (80, 80, 255), 2)

        # ── Center crosshair ──────────────────────────────────────────────────
        cv2.line(frame, (cx_frame - 20, cy_frame), (cx_frame + 20, cy_frame), (255, 255, 255), 1)
        cv2.line(frame, (cx_frame, cy_frame - 20), (cx_frame, cy_frame + 20), (255, 255, 255), 1)

        # ── HUD bottom-left ───────────────────────────────────────────────────
        cv2.putText(frame, f"dist : {distance_cm:.0f} cm",
                    (10, h - 80), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        cv2.putText(frame, f"off x: {off_x:+.2f}",
                    (10, h - 58), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        cv2.putText(frame, f"off y: {off_y:+.2f}",
                    (10, h - 36), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        cv2.putText(frame, f"servo: H={int(servo_h)} V={int(servo_v)}",
                    (10, h - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

        # ── Write shared memory + files ───────────────────────────────────────
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_ctr += 1
        meta = {
            "face":     bool(tracking),
            "cx":       int(face_cx),
            "cy":       int(face_cy),
            "dist":     round(float(distance_cm), 1),
            "off_x":    round(float(off_x), 3),
            "off_y":    round(float(off_y), 3),
            "tracking": bool(tracking),
            "servo_h":  servo_h,
            "servo_v":  servo_v,
        }
        _write_frame(frame_rgb, frame_ctr)
        _write_meta(meta)
        _write_files(frame_rgb, meta)

        cv2.imshow("Face Track", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord(" "):
            paused = not paused
        elif key == ord("r"):
            servo_h = SERVO_H_CENTER
            servo_v = SERVO_V_CENTER
            last_sent_h = SERVO_H_CENTER
            last_sent_v = SERVO_V_CENTER
            _send_servo("H", servo_h)
            _send_servo("V", servo_v)
            print(f"[face_track] servos reset to H={SERVO_H_CENTER} V={SERVO_V_CENTER}")

finally:
    cap.release()
    cv2.destroyAllWindows()
    if _sock:
        _sock.close()
    shm_frame.close()
    shm_meta.close()
    try:
        shm_frame.unlink()
    except Exception:
        pass
    try:
        shm_meta.unlink()
    except Exception:
        pass
    print("[face_track] cleanup done")
