# AURA Robot Face — Pan-Tilt Tracking System

Real-time face-tracking robot head built on an ESP32. A Python script detects faces via webcam and drives two servos (pan/tilt) to follow the subject. A Godot 4 desktop app provides a live camera feed, expression controls, and manual servo sliders.

---

## Architecture

```
Webcam
  └─► face_track.py  ──TCP:9000──┐
                                  ├─► serial_bridge.py ──Serial──► ESP32 (robot_face.ino)
Godot UI (RobotBridge.gd) ──TCP:6551──┘                               ├─ 2× Servo (pan/tilt)
     │                                                                  └─ 50× WS2811 LEDs
     └─► /tmp/robot_frame.bin  ◄── face_track.py (camera preview IPC)
         /tmp/robot_meta.json
```

**`serial_bridge.py`** is the hub — it owns the serial port and fans commands from two TCP sources into one write queue with per-axis servo deduplication.

---

## Hardware

| Component | Pin | Notes |
|-----------|-----|-------|
| Servo H (pan) | 9 | Center = 80° |
| Servo V (tilt) | 8 | Center = 60° |
| WS2811 LED strip | 12 | 50 LEDs, `FASTLED_ALLOW_INTERRUPTS 1` required |
| Status LED | 2 | Built-in, blinks on command receipt |

Serial: **9600 baud** (see Known Issues).

---

## Quickstart

### 1. Flash firmware

Open `robot_face.ino` in Arduino IDE, select your ESP32 board, and upload. The serial monitor should print `READY` at 9600 baud.

### 2. Install Python dependencies

```bash
pip install pyserial opencv-python mediapipe
```

`mediapipe` is optional — the tracker falls back to Haar Cascade if it's missing.

### 3. Start the bridge

```bash
python3 serial_bridge.py          # auto-detects Arduino port
# or
python3 serial_bridge.py /dev/tty.usbserial-XXXX
```

Wait for `Arduino ready.` before proceeding.

### 4. Start face tracking

```bash
python3 face_track.py
```

Press `q` in the preview window to quit.

### 5. Open Godot UI (optional)

Open the project in Godot 4.5 and press Play. The UI connects to the bridge on port 6551.

---

## Serial command reference

Sent over TCP to the bridge (or directly via Serial Monitor at 9600):

```
expr:neutral_open       # LED expression
expr:neutral_close
expr:sad
expr:angry
servo:h:<0-180>         # absolute pan angle
servo:v:<0-180>         # absolute tilt angle
servo:center            # return to H=80 V=60
sweep:h / sweep:v       # slow sweep
sweep:h:fast            # fast sweep
sweep:nod / sweep:shake # gesture
```

---

## Project status

**Working:**
- Face detection pipeline (MediaPipe primary, Haar fallback)
- Servo pan/tilt follows detected face at ~20Hz
- LED expressions triggered from Godot or serial
- Multi-client TCP bridge (Godot + face_track share the serial port)
- Godot UI: camera preview, expression buttons, manual servo sliders, command log

**Not yet implemented:**
- Process manager / startup script (3 processes must be started manually)
- Emotion-driven expressions (face_track detects position only, not mood)
- Servo speed limiting / acceleration curves
- MQTT integration with the broader AURA system

---

## Known problems

| Problem | Impact | Fix |
|---------|--------|-----|
| **Baud mismatch** | Bridge defaults to 115200; firmware uses 9600 — garbled serial | Either change `BAUD = 9600` in `serial_bridge.py` **or** change `Serial.begin(115200)` in firmware and reflash |
| **`/tmp` IPC** | Camera preview only works on macOS/Linux; Windows has no `/tmp` | Replace with a named pipe or small local HTTP server |
| **Focal length hardcoded** | Distance estimate (`dist` in UI) will be wrong for non-standard cameras | Run `camera.py` with a known object size to calibrate `FOCAL_LENGTH` |
| **Servo gain hardcoded** | H±40°, V±30° sweep may over/undershoot on different mounts | Tune `GAIN_H` / `GAIN_V` in `face_track.py` for your physical setup |
| **No reconnect on bridge crash** | face_track auto-reconnects, but Godot does not re-attempt after a failed connect | Add retry loop in `RobotBridge.gd` `_process` |
| **Single camera index** | `CAMERA_INDEX = 0` — fails silently if another app holds the camera | Expose as CLI arg or auto-scan |
