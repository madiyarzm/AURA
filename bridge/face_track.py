"""
face_track.py — Face detection + servo tracking + shared memory output

Shared memory "robot_frame": live RGB frame for Godot
Shared memory "robot_meta": JSON metadata (tracking, dist, offsets, servo pos)
TCP servo control via bridge on localhost:9000

    pip install opencv-python mediapipe
    python face_track.py

Hotkeys: Q=quit  SPACE=pause/resume  R=reset servos
"""

import cv2
import json
import mediapipe as mp
import os
import socket
import struct
import tempfile
import time
from multiprocessing.shared_memory import SharedMemory

FILE_FRAME = "/tmp/robot_frame.bin"
FILE_META = "/tmp/robot_meta.json"

CAMERA_INDEX = 0
KNOWN_FACE_WIDTH_CM = 16.0
FOCAL_LENGTH = 600
DETECTION_CONFIDENCE = 0.7  # minimum MediaPipe confidence to accept a detection

SERVO_H_CENTER = 80
SERVO_V_CENTER = 60
SERVO_H_MIN = 30
SERVO_H_MAX = 220
SERVO_V_MIN = 30
SERVO_V_MAX = 120
SERVO_H_GAIN = 40
SERVO_V_GAIN = 30
DEADZONE = 0.15
SEND_INTERVAL = 0.2
SMOOTH = 0.15
SMOOTH_RETURN = 0.05
INVERT_H = False
INVERT_V = False

BRIDGE_HOST = "localhost"
BRIDGE_PORT = 9000

FRAME_W = 640
FRAME_H = 480
FRAME_SHM_SIZE = 12 + FRAME_W * FRAME_H * 3
META_SHM_SIZE = 256

_H_DIR = -1 if INVERT_H else 1
_V_DIR = -1 if INVERT_V else 1


def _create_or_attach(name: str, size: int) -> SharedMemory:
    try:
        shm = SharedMemory(name=name, create=True, size=size)
    except FileExistsError:
        shm = SharedMemory(name=name, create=False, size=size)
    return shm


shm_frame = _create_or_attach("robot_frame", FRAME_SHM_SIZE)
shm_meta = _create_or_attach("robot_meta", META_SHM_SIZE)
print("[face_track] shared memory ready")


def _write_frame(frame_rgb, counter: int) -> None:
    buf = shm_frame.buf
    struct.pack_into(">III", buf, 0, counter, FRAME_W, FRAME_H)
    flat = frame_rgb.tobytes()
    buf[12 : 12 + len(flat)] = flat


def _write_meta(raw: bytes) -> None:
    padded = raw[: META_SHM_SIZE - 1].ljust(META_SHM_SIZE, b"\x00")
    shm_meta.buf[:META_SHM_SIZE] = padded


def _write_files(frame_rgb, meta_raw: str) -> None:
    """Write frame + meta to /tmp atomically so Godot never reads a partial file."""
    try:
        pixels = frame_rgb.tobytes()
        fd, tmp = tempfile.mkstemp(dir="/tmp", suffix=".bin")
        try:
            os.write(fd, pixels)
        finally:
            os.close(fd)
        os.replace(tmp, FILE_FRAME)
    except Exception as e:
        print(f"[face_track] frame write error: {e}")
    try:
        fd, tmp = tempfile.mkstemp(dir="/tmp", suffix=".json")
        try:
            os.write(fd, meta_raw.encode("utf-8"))
        finally:
            os.close(fd)
        os.replace(tmp, FILE_META)
    except Exception as e:
        print(f"[face_track] meta write error: {e}")


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
    try:
        _sock.sendall(f"servo:{axis.upper()}:{angle}\n".encode("utf-8"))
    except OSError:
        pass


servo_h = float(SERVO_H_CENTER)
servo_v = float(SERVO_V_CENTER)
last_sent_h = SERVO_H_CENTER
last_sent_v = SERVO_V_CENTER
last_send = 0.0


def _maybe_send_servos(off_x: float, off_y: float, use_deadzone: bool = True) -> None:
    """Send servo commands if rate limit elapsed and movement exceeds thresholds."""
    global last_sent_h, last_sent_v, last_send
    now = time.monotonic()
    if now - last_send < SEND_INTERVAL:
        return
    last_send = now
    if use_deadzone and abs(off_x) < DEADZONE and abs(off_y) < DEADZONE:
        return
    ih, iv = int(round(servo_h)), int(round(servo_v))
    if abs(ih - last_sent_h) >= 3:
        _send_servo("H", ih)
        last_sent_h = ih
    if abs(iv - last_sent_v) >= 3:
        _send_servo("V", iv)
        last_sent_v = iv


if _connect_bridge():
    print("[face_track] bridge connected")
    _send_servo("H", SERVO_H_CENTER)
    _send_servo("V", SERVO_V_CENTER)
    time.sleep(0.1)
    print(f"[face_track] servos initialized to center H={SERVO_H_CENTER} V={SERVO_V_CENTER}")
else:
    print("[face_track] bridge not available (continuing without servo output)")

_mp_face = mp.solutions.face_detection.FaceDetection(
    model_selection=0,  # 0 = short-range (≤2 m), 1 = full-range
    min_detection_confidence=DETECTION_CONFIDENCE,
)

cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)

if not cap.isOpened():
    print(f"[face_track] could not open camera {CAMERA_INDEX}")
    shm_frame.close()
    shm_frame.unlink()
    shm_meta.close()
    shm_meta.unlink()
    exit(1)

print(f"[face_track] camera open: {FRAME_W}x{FRAME_H}")
print("Hotkeys: Q=quit  SPACE=pause/resume  R=reset servos")

paused = False
frame_ctr = 0

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        cx_frame, cy_frame = w // 2, h // 2

        tracking = False
        face_cx, face_cy = cx_frame, cy_frame
        distance_cm = 0.0
        off_x = off_y = 0.0

        if not paused:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = _mp_face.process(rgb)

            if results.detections:
                tracking = True
                # pick the largest face by bounding box area
                det = max(
                    results.detections,
                    key=lambda d: d.location_data.relative_bounding_box.width
                                 * d.location_data.relative_bounding_box.height,
                )
                bb = det.location_data.relative_bounding_box
                x = max(0, int(bb.xmin * w))
                y = max(0, int(bb.ymin * h))
                bw = int(bb.width * w)
                bh = int(bb.height * h)

                face_cx = x + bw // 2
                face_cy = y + bh // 2
                distance_cm = (KNOWN_FACE_WIDTH_CM * FOCAL_LENGTH) / bw
                off_x = (face_cx - cx_frame) / (w / 2)
                off_y = (face_cy - cy_frame) / (h / 2)

                target_h = SERVO_H_CENTER + _H_DIR * off_x * SERVO_H_GAIN
                target_v = SERVO_V_CENTER + _V_DIR * off_y * SERVO_V_GAIN
                target_h = max(SERVO_H_MIN, min(SERVO_H_MAX, target_h))
                target_v = max(SERVO_V_MIN, min(SERVO_V_MAX, target_v))
                servo_h += (target_h - servo_h) * SMOOTH
                servo_v += (target_v - servo_v) * SMOOTH
                _maybe_send_servos(off_x, off_y)

                cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 220, 100), 2)
                l, t = 16, 3
                for px, py, dx, dy in [
                    (x, y, 1, 1), (x + bw, y, -1, 1),
                    (x, y + bh, 1, -1), (x + bw, y + bh, -1, -1),
                ]:
                    cv2.line(frame, (px, py), (px + dx * l, py), (0, 255, 120), t)
                    cv2.line(frame, (px, py), (px, py + dy * l), (0, 255, 120), t)
                cv2.circle(frame, (face_cx, face_cy), 4, (0, 220, 100), -1)
                cv2.line(frame, (cx_frame, cy_frame), (face_cx, face_cy), (0, 180, 80), 1)
                cv2.putText(frame, f"{distance_cm:.0f} cm", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 100), 2)
                cv2.putText(frame, "FACE DETECTED", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 100), 2)
            else:
                servo_h += (SERVO_H_CENTER - servo_h) * SMOOTH_RETURN
                servo_v += (SERVO_V_CENTER - servo_v) * SMOOTH_RETURN
                _maybe_send_servos(off_x, off_y, use_deadzone=False)
                cv2.putText(frame, "no face", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (80, 80, 255), 2)
        else:
            cv2.putText(frame, "PAUSED", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (80, 80, 255), 2)

        cv2.line(frame, (cx_frame - 20, cy_frame), (cx_frame + 20, cy_frame), (255, 255, 255), 1)
        cv2.line(frame, (cx_frame, cy_frame - 20), (cx_frame, cy_frame + 20), (255, 255, 255), 1)

        cv2.putText(frame, f"dist : {distance_cm:.0f} cm", (10, h - 80), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        cv2.putText(frame, f"off x: {off_x:+.2f}", (10, h - 58), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        cv2.putText(frame, f"off y: {off_y:+.2f}", (10, h - 36), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        cv2.putText(frame, f"servo: H={int(servo_h)} V={int(servo_v)}", (10, h - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_ctr += 1
        meta_str = json.dumps({
            "tracking": bool(tracking),
            "cx": int(face_cx),
            "cy": int(face_cy),
            "dist": round(float(distance_cm), 1),
            "off_x": round(float(off_x), 3),
            "off_y": round(float(off_y), 3),
            "servo_h": servo_h,
            "servo_v": servo_v,
        })
        _write_frame(frame_rgb, frame_ctr)
        _write_meta(meta_str.encode("utf-8"))
        _write_files(frame_rgb, meta_str)

        cv2.imshow("Face Track", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord(" "):
            paused = not paused
        elif key == ord("r"):
            servo_h = float(SERVO_H_CENTER)
            servo_v = float(SERVO_V_CENTER)
            last_sent_h = SERVO_H_CENTER
            last_sent_v = SERVO_V_CENTER
            _send_servo("H", SERVO_H_CENTER)
            _send_servo("V", SERVO_V_CENTER)
            print(f"[face_track] servos reset to H={SERVO_H_CENTER} V={SERVO_V_CENTER}")

finally:
    _mp_face.close()
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
