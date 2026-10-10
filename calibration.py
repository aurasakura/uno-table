"""
Calibration: clicking points in the camera view, and saving/loading calibration.json.

calibration.json looks like:
{
  "test":      {"cam_points": [[x, y] x4], "frame_size": [w, h]},
  "projector": {"cam_points": [[x, y] x4], "proj_points": [[x, y] x4],
                "frame_size": [w, h], "placement": {...}}
}
"""
import json
import os

import cv2
import numpy as np

import config as C


# ---------------------------------------------------------------------
# File
# ---------------------------------------------------------------------
def load(mode):
    """Calibration section for 'test' or 'projector' (empty dict if none saved)."""
    if not os.path.exists(C.CALIBRATION_FILE):
        return {}
    try:
        with open(C.CALIBRATION_FILE) as f:
            return json.load(f).get(mode, {})
    except (OSError, ValueError) as e:
        print(f"[calibration] could not read {C.CALIBRATION_FILE}: {e}")
        return {}


def save(mode, section):
    data = {}
    if os.path.exists(C.CALIBRATION_FILE):
        try:
            with open(C.CALIBRATION_FILE) as f:
                data = json.load(f)
        except (OSError, ValueError):
            pass
    data[mode] = section
    with open(C.CALIBRATION_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[calibration] saved '{mode}' to {C.CALIBRATION_FILE}")


# ---------------------------------------------------------------------
# Homographies
# ---------------------------------------------------------------------
def board_corners():
    B = C.BOARD_PX
    return np.float32([[0, 0], [B, 0], [B, B], [0, B]])


def homography(src_pts, dst_pts):
    return cv2.getPerspectiveTransform(np.float32(src_pts), np.float32(dst_pts))


# ---------------------------------------------------------------------
# Drawing helper (shared with main.py)
# ---------------------------------------------------------------------
def put_label(img, text, org, scale=0.6, colour=(255, 255, 255)):
    """Text with a dark background box so it is readable on any image."""
    (w, h), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    x, y = org
    cv2.rectangle(img, (x - 3, y - h - 4), (x + w + 3, y + base + 2), (0, 0, 0), -1)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, colour, 1, cv2.LINE_AA)


# ---------------------------------------------------------------------
# Interactive clicking
# ---------------------------------------------------------------------
def click_points(cap, window, prompts, on_step=None):
    """
    Show the live camera in `window` and let the user click one point per prompt.
      left click = place point, right click = undo, Enter = accept, Esc = cancel.
    on_step(i) is called every frame with the index of the point being asked for
    (used in projector mode to show only that dot).
    Returns a list of (x, y) or None if cancelled.
    """
    pts = []
    n = len(prompts)

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(pts) < n:
            pts.append((x, y))
            print(f"  point {len(pts)}: ({x}, {y})")
        elif event == cv2.EVENT_RBUTTONDOWN and pts:
            pts.pop()

    cv2.setMouseCallback(window, on_mouse)
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                if cv2.waitKey(30) & 0xFF == 27:
                    return None
                continue
            i = len(pts)
            if on_step:
                on_step(min(i, n - 1))
            vis = frame.copy()
            for j, p in enumerate(pts):
                cv2.circle(vis, p, 6, (0, 255, 255), -1)
                cv2.putText(vis, str(j + 1), (p[0] + 8, p[1] - 8), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0, 255, 255), 2)
            if len(pts) > 1:
                cv2.polylines(vis, [np.int32(pts)], len(pts) == n, (0, 255, 255), 2)
            if i < n:
                put_label(vis, f"CALIBRATE {i + 1}/{n}: click {prompts[i]}", (10, 30), 0.7)
            else:
                put_label(vis, "Enter = accept", (10, 30), 0.7, (0, 255, 0))
            put_label(vis, "right-click = undo    Esc = cancel", (10, 60))
            cv2.imshow(window, vis)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                print("[calibration] cancelled")
                return None
            if key in (13, 10) and len(pts) == n:
                return pts
    finally:
        cv2.setMouseCallback(window, lambda *a: None)
