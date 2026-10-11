"""
Interactive UNO table.

  python main.py               # mode from config.TEST_MODE
  python main.py --test        # force test mode (laptop + phone only)
  python main.py --projector   # force projector mode
  python main.py --camera 2    # override camera index (or a DroidCam URL)
  python main.py --probe       # show every camera index so you can find DroidCam
"""
import argparse
import random
import sys
import time

import cv2
import numpy as np

import calibration
import config as C
from calibration import put_label
from detector import Card, CardDetector, classify_hsv_pixel, detect_rect, zone_rect
from projector import Placement, dot_frame
from reactions import Stage

WIN_CAM = "Camera"
WIN_DEBUG = "Debug (top-down view)"
WIN_PROJ = "Projector"

# cv2.waitKeyEx codes for arrow keys (Windows, then Linux)
ARROWS = {2424832: (-1, 0), 2555904: (1, 0), 2490368: (0, -1), 2621440: (0, 1),
          65361: (-1, 0), 65363: (1, 0), 65362: (0, -1), 65364: (0, 1)}
IJKL = {ord("j"): (-1, 0), ord("l"): (1, 0), ord("i"): (0, -1), ord("k"): (0, 1)}
FAKE_COLOURS = {ord("r"): "red", ord("y"): "yellow", ord("g"): "green", ord("b"): "blue", ord("w"): "wild"}
FAKE_ACTIONS = {ord("1"): "skip", ord("2"): "draw2", ord("3"): "reverse", ord("4"): "wild4"}

HELP = """
---------------------------------------------------------------
 Keys (click on any of the app windows first so it has focus)
   c          calibrate
   space      re-learn the empty discard zone (zone must be empty)
   r y g b w  fake a red / yellow / green / blue / wild card
   1 2 3 4    fake skip / +2 / reverse / wild +4
   h          show this help          q or Esc   quit
 Projector mode only
   arrows or i j k l   move the square      + / -   resize
   o  rotate 90        x  mirror on/off     f  fullscreen on/off
   s  save projector placement
 Debug window: left-click a pixel to print its colour values
---------------------------------------------------------------"""


def open_camera(src):
    if isinstance(src, str) and not src.isdigit():
        cap = cv2.VideoCapture(src)                      # DroidCam URL
    else:
        backend = {"dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF}.get(C.CAMERA_BACKEND, cv2.CAP_ANY)
        cap = cv2.VideoCapture(int(src), backend)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, C.CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, C.CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)                  # keep latency low
    return cap


def probe_cameras(max_index=5):
    print("Probing cameras... each working one is shown for 3 seconds.")
    for i in range(max_index):
        cap = open_camera(i)
        ok, frame = cap.read() if cap.isOpened() else (False, None)
        if not ok:
            print(f"  index {i}: nothing")
            cap.release()
            continue
        print(f"  index {i}: OK {frame.shape[1]}x{frame.shape[0]}")
        end = time.time() + 3
        while time.time() < end:
            ok, frame = cap.read()
            if ok:
                put_label(frame, f"camera index {i}", (10, 30), 0.9)
                cv2.imshow("probe", frame)
            cv2.waitKey(1)
        cap.release()
    cv2.destroyAllWindows()
    print("Put the index that shows your phone into CAMERA_INDEX in config.py (or use --camera N).")


class App:
    def __init__(self, test_mode, cam_src, collect=None):
        self.collect = collect      # symbol label: save every read card crop to dataset/raw/<label>/
        self.test_mode = test_mode
        self.mode = "test" if test_mode else "projector"
        self.cap = open_camera(cam_src)
        if not self.cap.isOpened():
            sys.exit(f"Could not open camera {cam_src!r}. Is DroidCam connected? "
                     f"Try `python main.py --probe` or another --camera index.")

        self.calib = calibration.load(self.mode)
        self.placement = Placement.from_dict(self.calib.get("placement"))
        self.H = None                   # camera px -> board px
        self.detector = CardDetector()
        self.stage = Stage()
        self.board_view = None          # last top-down camera image
        self.frame_size = None
        self.click_info = None
        self.fullscreen = False

        cv2.namedWindow(WIN_CAM, cv2.WINDOW_NORMAL)
        cv2.namedWindow(WIN_DEBUG, cv2.WINDOW_NORMAL)
        cv2.namedWindow(WIN_PROJ, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(WIN_DEBUG, self.on_debug_click)
        if self.test_mode:
            cv2.resizeWindow(WIN_PROJ, C.TEST_PROJECTOR_WINDOW_PX, C.TEST_PROJECTOR_WINDOW_PX)
        else:
            cv2.moveWindow(WIN_PROJ, C.PROJECTOR_SCREEN_X, C.PROJECTOR_SCREEN_Y)
            self.set_fullscreen(C.PROJECTOR_START_FULLSCREEN)
        self.update_homography()
        print(f"Mode: {self.mode.upper()}   camera: {cam_src!r}")
        if not self.test_mode:
            print(f"Projector placement: {self.placement}")
        print(HELP)
        if self.H is None:
            print(">>> Not calibrated yet: press C." if self.test_mode else
                  ">>> Not calibrated yet: first move/resize the square so it fits the table, then press C.")

    # -----------------------------------------------------------------
    # Calibration
    # -----------------------------------------------------------------
    def update_homography(self):
        pts = self.calib.get("cam_points")
        if not pts:
            self.H = None
        elif self.test_mode:
            self.H = calibration.homography(pts, calibration.board_corners())
        else:
            cam_to_proj = calibration.homography(pts, self.calib["proj_points"])
            self.H = np.linalg.inv(self.placement.matrix()) @ cam_to_proj
        self.detector.reset()

    def calibrate(self):
        if self.test_mode:
            prompts = ["the TOP-LEFT corner of the paper", "the TOP-RIGHT corner",
                       "the BOTTOM-RIGHT corner", "the BOTTOM-LEFT corner"]
            pts = calibration.click_points(self.cap, WIN_CAM, prompts)
            if pts is None:
                return
            self.calib = {"cam_points": pts, "frame_size": self.frame_size}
        else:
            B, m = C.BOARD_PX, C.CALIB_DOT_INSET * C.BOARD_PX
            proj_pts = self.placement.board_to_projector([[m, m], [B - m, m], [B - m, B - m], [m, B - m]])
            prompts = [f"the projected white dot ({i + 1} of 4)" for i in range(4)]
            show_dot = lambda i: cv2.imshow(WIN_PROJ, dot_frame(proj_pts[i]))
            pts = calibration.click_points(self.cap, WIN_CAM, prompts, show_dot)
            if pts is None:
                return
            self.calib = {"cam_points": pts, "proj_points": proj_pts.tolist(),
                          "frame_size": self.frame_size, "placement": self.placement.to_dict()}
        calibration.save(self.mode, self.calib)
        self.update_homography()
        print("Calibrated. Keep the discard zone EMPTY for a second so it learns the empty zone.")

    def save_placement(self):
        self.calib["placement"] = self.placement.to_dict()
        calibration.save(self.mode, self.calib)

    # -----------------------------------------------------------------
    # Debug
    # -----------------------------------------------------------------
    def on_debug_click(self, event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN or self.board_view is None:
            return
        patch = self.board_view[max(0, y - 2):y + 3, max(0, x - 2):x + 3].reshape(-1, 3)
        bgr = patch.mean(0).astype(np.uint8)
        h, s, v = cv2.cvtColor(bgr.reshape(1, 1, 3), cv2.COLOR_BGR2HSV)[0, 0]
        cls = classify_hsv_pixel(int(h), int(s), int(v))
        self.click_info = (x, y, f"BGR={tuple(int(c) for c in bgr)} HSV=({h},{s},{v}) -> {cls}")
        print(f"[pixel] board ({x},{y}) 5x5 avg  {self.click_info[2]}")

    def draw_camera_view(self, frame):
        vis = frame.copy()
        if self.H is not None:
            x0, y0, x1, y1 = zone_rect()
            B = C.BOARD_PX
            corners = np.float32([[[0, 0]], [[B, 0]], [[B, B]], [[0, B]]])
            zone = np.float32([[[x0, y0]], [[x1, y0]], [[x1, y1]], [[x0, y1]]])
            Hinv = np.linalg.inv(self.H)
            cv2.polylines(vis, [np.int32(cv2.perspectiveTransform(corners, Hinv))], True, (0, 255, 255), 2)
            cv2.polylines(vis, [np.int32(cv2.perspectiveTransform(zone, Hinv))], True, (0, 255, 0), 2)
            put_label(vis, f"{self.mode} mode   C = recalibrate   H = help", (10, 30))
        else:
            put_label(vis, "NOT CALIBRATED - press C", (10, 30), 0.8, (0, 0, 255))
        cv2.imshow(WIN_CAM, vis)

    def draw_debug_view(self):
        if self.board_view is None:
            img = np.zeros((C.BOARD_PX, C.BOARD_PX, 3), np.uint8)
            put_label(img, "calibrate first (press C)", (20, 40), 0.8)
            cv2.imshow(WIN_DEBUG, img)
            return
        img = self.board_view.copy()
        x0, y0, x1, y1 = zone_rect()
        cv2.rectangle(img, (x0, y0), (x1, y1), (0, 255, 0), 2)
        dx0, dy0, dx1, dy1 = detect_rect()
        cv2.rectangle(img, (dx0, dy0), (dx1, dy1), (0, 200, 255), 1)
        d = self.detector
        put_label(img, f"state: {d.status}", (10, 25))
        put_label(img, f"motion {d.motion:.3f} (still<{C.STILL_MAX_FRACTION})   "
                       f"change {d.change:.3f} (new>{C.CHANGE_MIN_FRACTION})", (10, 50), 0.5)
        put_label(img, f"live colour: {d.live_label}   last card: {self.stage.last_card}", (10, 75), 0.5)
        # colour fraction bars
        bar_colours = {**C.DRAW_COLOURS, "black": (128, 128, 128)}
        for i, name in enumerate(("red", "yellow", "green", "blue", "black")):
            f = d.fractions.get(name, 0.0)
            y = C.BOARD_PX - 20 - i * 22
            limit = C.MIN_BLACK_FRACTION if name == "black" else C.MIN_COLOUR_FRACTION
            cv2.rectangle(img, (70, y - 12), (70 + int(f * 400), y + 4), bar_colours[name], -1)
            cv2.line(img, (70 + int(limit * 400), y - 14), (70 + int(limit * 400), y + 6), (255, 255, 255), 1)
            put_label(img, f"{name[:3]} {f:.2f}", (5, y), 0.4)
        if self.click_info:
            cx, cy, text = self.click_info
            cv2.drawMarker(img, (cx, cy), (255, 0, 255), cv2.MARKER_CROSS, 14, 2)
            put_label(img, text, (10, 100), 0.45, (255, 0, 255))
        cv2.imshow(WIN_DEBUG, img)

    # -----------------------------------------------------------------
    # Output
    # -----------------------------------------------------------------
    def show_projector(self, board):
        if self.test_mode:
            cv2.imshow(WIN_PROJ, board)
        else:
            cv2.imshow(WIN_PROJ, self.placement.render(board))

    def set_fullscreen(self, on):
        self.fullscreen = on
        cv2.setWindowProperty(WIN_PROJ, cv2.WND_PROP_FULLSCREEN,
                              cv2.WINDOW_FULLSCREEN if on else cv2.WINDOW_NORMAL)

    def fake_card(self, key, now):
        if key in FAKE_COLOURS:
            card = Card(FAKE_COLOURS[key])
        else:
            symbol = FAKE_ACTIONS[key]
            last = self.stage.last_card
            colour = "wild" if symbol == "wild4" else (
                last.colour if last and last.colour != "wild" else random.choice(["red", "yellow", "green", "blue"]))
            card = Card(colour, symbol)
        print(f"[fake] {card}")
        self.stage.trigger(card, now)

    # -----------------------------------------------------------------
    # Main loop
    # -----------------------------------------------------------------
    def handle_key(self, key, now):
        """Returns False to quit."""
        if key == -1:
            return True
        ch = key if key < 256 else None
        if ch is not None and ord("A") <= ch <= ord("Z"):      # Caps Lock / Shift still work
            ch += 32
        if ch in (ord("q"), 27):
            return False
        if ch == ord("c"):
            self.calibrate()
        elif ch == ord(" "):
            self.detector.reset()
            print("Re-learning the empty zone...")
        elif ch == ord("h"):
            print(HELP)
        elif ch in FAKE_COLOURS or ch in FAKE_ACTIONS:
            self.fake_card(ch, now)
        elif not self.test_mode:
            moved = True
            if key in ARROWS or ch in IJKL:
                self.placement.move(*(ARROWS.get(key) or IJKL[ch]))
            elif ch in (ord("+"), ord("=")):
                self.placement.resize(+1)
            elif ch in (ord("-"), ord("_")):
                self.placement.resize(-1)
            elif ch == ord("o"):
                self.placement.rotate_cw()
            elif ch == ord("x"):
                self.placement.toggle_mirror()
            else:
                moved = False
            if moved:
                print(f"Projector placement: {self.placement}   (press S to save)")
                self.update_homography()
            elif ch == ord("f"):
                self.set_fullscreen(not self.fullscreen)
            elif ch == ord("s"):
                self.save_placement()
        return True

    def save_crop(self, now):
        import os
        folder = os.path.join("dataset", "raw", self.collect)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{int(now * 1000)}.jpg")
        cv2.imwrite(path, self.detector.last_card_img)
        print(f"[collect] saved {path}  ({len(os.listdir(folder))} in {self.collect})")

    def run(self):
        fails = 0
        while True:
            ok, frame = self.cap.read()
            now = time.time()
            if not ok:
                fails += 1
                if fails % 30 == 1:
                    print("No camera frame - is DroidCam running and connected?")
                if not self.handle_key(cv2.waitKeyEx(30), now):
                    break
                continue
            fails = 0
            size = [frame.shape[1], frame.shape[0]]
            if self.frame_size is None:
                self.frame_size = size
                saved = self.calib.get("frame_size")
                if saved and saved != size:
                    print(f"WARNING: calibration was made at {saved}, camera now gives {size}. Recalibrate (C).")

            if self.H is not None:
                self.board_view = cv2.warpPerspective(frame, self.H, (C.BOARD_PX, C.BOARD_PX))
                card = self.detector.update(self.board_view, now)
                if card:
                    print(f"[detect] new card: {card}   scores "
                          + " ".join(f"{k}={v:.2f}" for k, v in card.scores.items()))
                    self.stage.trigger(card, now)
                    if self.collect:
                        self.save_crop(now)
            else:
                self.board_view = None

            self.show_projector(self.stage.render(now))
            self.draw_camera_view(frame)
            self.draw_debug_view()
            if not self.handle_key(cv2.waitKeyEx(1), now):
                break
        self.cap.release()
        cv2.destroyAllWindows()


def main():
    ap = argparse.ArgumentParser(description="Interactive UNO table")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--test", action="store_true", help="test mode (no projector)")
    g.add_argument("--projector", action="store_true", help="projector mode")
    ap.add_argument("--camera", help="camera index or DroidCam URL (overrides config)")
    ap.add_argument("--collect", metavar="LABEL",
                    help="save each read card crop to dataset/raw/LABEL (0-9 skip reverse draw2 wild wild4)")
    ap.add_argument("--probe", action="store_true", help="show all camera indexes and exit")
    args = ap.parse_args()

    if args.probe:
        probe_cameras()
        return
    test_mode = True if args.test else False if args.projector else C.TEST_MODE
    cam = args.camera if args.camera is not None else C.CAMERA_INDEX
    App(test_mode, cam, args.collect).run()


if __name__ == "__main__":
    main()
