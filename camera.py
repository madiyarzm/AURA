"""
face_check.py — Standalone face detection test
===============================================
Uses built-in camera, draws a box around your face,
estimates distance, and shows offset from center.

No bridge, no Arduino needed — just a camera test.

    pip install opencv-python
    python face_check.py

Press Q to quit.
"""

import cv2

# ── Config ────────────────────────────────────────────────────────────────────
CAMERA_INDEX = 0  # 0 = built-in Mac cam

# Distance estimation calibration:
# Measure KNOWN_WIDTH (average human face ~16cm) and
# KNOWN_DISTANCE (how far you sat when you took reference photo in cm)
# then FOCAL_LENGTH = (box_width_in_pixels * KNOWN_DISTANCE) / KNOWN_WIDTH
KNOWN_FACE_WIDTH_CM = 16.0
FOCAL_LENGTH = 600  # tweak this until distance reads correctly for you

# ── Load OpenCV face detector (built-in, no install needed) ──────────────────
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

if not cap.isOpened():
    print(f"Could not open camera {CAMERA_INDEX}")
    exit(1)

print("Camera open. Press Q to quit.")
print("Tip: if distance reads wrong, adjust FOCAL_LENGTH at top of file.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    h, w = frame.shape[:2]
    cx_frame, cy_frame = w // 2, h // 2

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    faces = face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
    )

    # ── Draw center crosshair ─────────────────────────────────────────────────
    cv2.line(
        frame, (cx_frame - 20, cy_frame), (cx_frame + 20, cy_frame), (255, 255, 255), 1
    )
    cv2.line(
        frame, (cx_frame, cy_frame - 20), (cx_frame, cy_frame + 20), (255, 255, 255), 1
    )

    if len(faces) > 0:
        # Pick largest face
        x, y, bw, bh = max(faces, key=lambda f: f[2] * f[3])

        face_cx = x + bw // 2
        face_cy = y + bh // 2

        # Distance estimate
        distance_cm = (KNOWN_FACE_WIDTH_CM * FOCAL_LENGTH) / bw

        # Offset from frame center (normalised -1 to +1)
        off_x = (face_cx - cx_frame) / (w / 2)
        off_y = (face_cy - cy_frame) / (h / 2)

        # ── Draw face box ─────────────────────────────────────────────────────
        cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 220, 100), 2)

        # Corner accents
        l = 16  # corner length
        t = 3  # corner thickness
        for px, py, dx, dy in [
            (x, y, 1, 1),
            (x + bw, y, -1, 1),
            (x, y + bh, 1, -1),
            (x + bw, y + bh, -1, -1),
        ]:
            cv2.line(frame, (px, py), (px + dx * l, py), (0, 255, 120), t)
            cv2.line(frame, (px, py), (px, py + dy * l), (0, 255, 120), t)

        # Face center dot
        cv2.circle(frame, (face_cx, face_cy), 4, (0, 220, 100), -1)

        # Line from frame center to face center
        cv2.line(frame, (cx_frame, cy_frame), (face_cx, face_cy), (0, 180, 80), 1)

        # ── Labels ────────────────────────────────────────────────────────────
        label = f"{distance_cm:.0f} cm"
        cv2.putText(
            frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 100), 2
        )

        # HUD bottom-left
        cv2.putText(
            frame,
            f"dist : {distance_cm:.0f} cm",
            (10, h - 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (200, 200, 200),
            1,
        )
        cv2.putText(
            frame,
            f"off x: {off_x:+.2f}",
            (10, h - 58),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (200, 200, 200),
            1,
        )
        cv2.putText(
            frame,
            f"off y: {off_y:+.2f}",
            (10, h - 36),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (200, 200, 200),
            1,
        )
        cv2.putText(
            frame,
            f"box  : {bw}x{bh}px",
            (10, h - 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (200, 200, 200),
            1,
        )

        cv2.putText(
            frame,
            "FACE DETECTED",
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 220, 100),
            2,
        )
    else:
        cv2.putText(
            frame, "no face", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (80, 80, 255), 2
        )

    cv2.imshow("Face Check", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
