"""
Interactive UNO table.

  python main.py               # mode from config.TEST_MODE
  python main.py --test        # force test mode (laptop + phone only)
  python main.py --projector   # force projector mode
  python main.py --camera 2    # override camera index (or a DroidCam URL)
  python main.py --probe       # show every camera index so you can find DroidCam
"""
import argparse
import copy
import os
import random
import sys
import time

import cv2
import numpy as np

import calibration
import config as C
import hud
import sound
from uno_call import UnoCallWatcher
from calibration import put_label
from detector import (Card, CardDetector, circle_hits_keepout, classify_hsv_pixel, detect_rect,
                      draw_pile_rect, zone_rect)
from game import Game
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
TABLE_EVENTS = {ord("u"): "uno", ord("d"): "draw", ord("v"): "win"}   # things the camera can't see
EVENT_REACTIONS = {"draw": "draw", "penalty": "draw", "uno": "uno", "win": "win"}   # game event -> reaction

HELP = """
---------------------------------------------------------------
 Keys (click on any of the app windows first so it has focus)
   c          calibrate
   space      re-learn the empty discard zone (zone must be empty)
   r y g b w  fake a red / yellow / green / blue / wild card
   1 2 3 4    fake skip / +2 / reverse / wild +4
   u          UNO! (player on 1 card, or the current player before playing)
   d          current player draws a card and passes
   z          undo the last play / draw / UNO call / penalty (then re-enter the right card)
   v          win effect (manual)       n   new game (4 players, 7 cards)
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
        self.game = Game()
        self.uno_watcher = UnoCallWatcher()
        self.undo_stack = []        # (game copy, stage.last_card, what was done) before each game action
        self.last_cam_warning = 0.0
        sound.init()
        self.projected = None       # last board image sent to the projector (uno_call ignores lit pixels)
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
            pts = self.click_quad(prompts)
            if pts is None:
                return
            self.calib = {"cam_points": pts, "frame_size": self.frame_size}
        else:
            B, m = C.BOARD_PX, C.CALIB_DOT_INSET * C.BOARD_PX
            board_pts = [[m, m], [B - m, m], [B - m, B - m], [m, B - m]]
            r = C.CALIB_DOT_RADIUS * B / self.placement.size      # dot radius in board px
            if any(circle_hits_keepout(x, y, r) for x, y in board_pts):
                print("WARNING: calibration dots touch the corner posts. Raise CALIB_DOT_INSET in config.py.")
            proj_pts = self.placement.board_to_projector(board_pts)
            prompts = [f"the projected white dot ({i + 1} of 4)" for i in range(4)]
            show_dot = lambda i: cv2.imshow(WIN_PROJ, dot_frame(proj_pts[i]))
            pts = self.click_quad(prompts, show_dot)
            if pts is None:
                return
            self.calib = {"cam_points": pts, "proj_points": proj_pts.tolist(),
                          "frame_size": self.frame_size, "placement": self.placement.to_dict()}
        calibration.save(self.mode, self.calib)
        self.update_homography()
        print("Calibrated. Keep the discard zone EMPTY for a second so it learns the empty zone.")

    def click_quad(self, prompts, on_step=None):
        """Clicked points, asking again until they form a usable shape. None if cancelled."""
        while True:
            pts = calibration.click_points(self.cap, WIN_CAM, prompts, on_step)
            problem = pts and calibration.quad_problem(pts)
            if not problem:
                return pts
            print(f"[calibration] {problem}. Click the 4 points again.")

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
            px0, py0, px1, py1 = draw_pile_rect()
            pile = np.float32([[[px0, py0]], [[px1, py0]], [[px1, py1]], [[px0, py1]]])
            cv2.polylines(vis, [np.int32(cv2.perspectiveTransform(pile, Hinv))], True, (255, 160, 0), 2)
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
        px0, py0, px1, py1 = draw_pile_rect()
        cv2.rectangle(img, (px0, py0), (px1, py1), (255, 160, 0), 2)
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
            card = Card(FAKE_COLOURS[key], fake=True)
        else:
            symbol = FAKE_ACTIONS[key]
            last = self.stage.last_card
            colour = "wild" if symbol == "wild4" else (
                last.colour if last and last.colour != "wild" else random.choice(["red", "yellow", "green", "blue"]))
            card = Card(colour, symbol, fake=True)
        print(f"[fake] {card}")
        self.play_card(card, now)

    # -----------------------------------------------------------------
    # Game
    # -----------------------------------------------------------------
    def act(self, what, fn):
        """Run one game action, keeping a copy of the game from before it for key Z."""
        before = (copy.deepcopy(self.game), self.stage.last_card, what, sound.state())
        events = fn()
        if any(e.kind not in ("info", "reject") for e in events):    # something changed
            self.undo_stack = (self.undo_stack + [before])[-C.UNDO_DEPTH:]
        return events

    def undo(self, now):
        if not self.undo_stack:
            print("[game] Undo: nothing to undo")
            return
        self.game, self.stage.last_card, what, snd = self.undo_stack.pop()
        sound.set_state(snd)
        self.stage.active.clear()          # stop effects of the undone action (e.g. a WIN)
        if self.game.uno_left(now) == 0.0 and self.game.uno_since is not None:
            self.game.uno_since = now      # countdown had expired: restart it, or the penalty comes straight back
        print(f"[game] Undo: {what}. {self.game.name(self.game.current)} to play"
              + ("" if self.game.started else " (no starting card yet)"))

    def play_card(self, card, now):
        prev_top, colour_unknown = self.game.top, self.game.colour_unknown
        events = self.act(f"card {card}", lambda: self.game.play(card, now))
        kinds = {e.kind for e in events}
        if kinds & {"start", "play"}:            # accepted: not refused, not after a win
            sound.on_card(card, prev_top, colour_unknown, events, now)
            self.stage.trigger(card, now)
        elif "reject" in kinds:
            sound.on_card(card, prev_top, colour_unknown, events, now)   # the illegal buzzer
        self.apply_events(events, now)

    def apply_events(self, events, now):
        """Print the game log and play the reaction for draws, UNO calls and wins."""
        for e in events:
            print(f"[game] {e.text}")
            sound.on_event(e, now)
            if e.kind in EVENT_REACTIONS:
                self.react(EVENT_REACTIONS[e.kind], now)

    def react(self, kind, now):
        last = self.stage.last_card
        self.stage.trigger(Card(last.colour if last else "wild", kind), now)
        self.stage.last_card = last        # an event is not a played card

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
        elif ch == ord("d"):
            events = self.act("draw", self.game.draw)
            if any(e.kind == "draw" for e in events):
                sound.play("draw", now)           # only key D; +2/+4/penalty draws have their own sounds
            self.apply_events(events, now)
        elif ch == ord("u"):
            self.apply_events(self.act("UNO call", lambda: self.game.call_uno(now)), now)
        elif ch == ord("z"):
            self.undo(now)
        elif ch == ord("n"):
            self.game = Game()
            self.stage.last_card = None
            self.stage.active.clear()
            self.detector.reset()           # the current zone becomes the empty baseline
            self.uno_watcher = UnoCallWatcher()
            self.undo_stack.clear()
            sound.reset()
            sound.play("start", now)
            print("[game] New game: 4 players, 7 cards each. The discard zone should be EMPTY now; "
                  "the next card on the pile is the starting card.")
        elif ch in TABLE_EVENTS:
            self.react(TABLE_EVENTS[ch], now)
            sound.play(TABLE_EVENTS[ch], now)
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
        folder = os.path.join("dataset", "raw", self.collect)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{int(now * 1000)}.jpg")
        cv2.imwrite(path, self.detector.last_card_img)
        print(f"[collect] saved {path}  ({len(os.listdir(folder))} in {self.collect})")

    def detect(self, frame, now):
        size = [frame.shape[1], frame.shape[0]]
        if self.frame_size is None:
            self.frame_size = size
            saved = self.calib.get("frame_size")
            if saved and saved != size:
                print(f"WARNING: calibration was made at {saved}, camera now gives {size}. Recalibrate (C).")
        if self.H is None:
            self.board_view = None
            return
        self.board_view = cv2.warpPerspective(frame, self.H, (C.BOARD_PX, C.BOARD_PX))
        card = self.detector.update(self.board_view, now, collect=bool(self.collect))
        if self.collect and self.detector.capture_ready:
            self.save_crop(now)             # unknown symbols are training data, not plays
        if card:
            print(f"[detect] new card: {card}   scores "
                  + " ".join(f"{k}={v:.2f}" for k, v in card.scores.items()))
            self.play_card(card, now)

    def step(self, frame, now):
        """One frame of the loop. frame is None when the camera gave nothing:
        the game, HUD and projector keep running, only detection stops."""
        if frame is not None:
            self.detect(frame, now)
        # Settle a UNO? window that ran out before a card back can call it.
        if C.UNO_WINDOW_SECONDS > 0 and self.game.uno_left(now) == 0.0:
            self.apply_events(self.act("UNO penalty", lambda: self.game.tick(now)), now)
        open_seat = self.game.uno_watch if self.game.uno_left(now) is not None else None
        self.uno_watcher.watch(open_seat)
        if (C.UNO_CALL_BY_CARD_BACK and frame is not None and self.board_view is not None
                and open_seat is not None
                and self.uno_watcher.update(self.board_view, now, self.projected)):
            print("[uno] card back seen")
            self.apply_events(self.act("UNO call", lambda: self.game.call_uno(now)), now)
        self.projected = self.stage.render(now, lambda b: hud.draw(b, self.game.snapshot(now), now))
        self.show_projector(self.projected)
        if frame is not None:
            self.draw_camera_view(frame)
            self.draw_debug_view()
        elif now - self.last_cam_warning >= 1.0:
            self.last_cam_warning = now
            print("CAMERA DISCONNECTED - is DroidCam running and connected?")
            w, h = self.frame_size or (640, 360)
            img = np.zeros((h, w, 3), np.uint8)
            put_label(img, "CAMERA DISCONNECTED", (10, 30), 0.6, (0, 0, 255))
            cv2.imshow(WIN_CAM, img)

    def run(self):
        while True:
            ok, frame = self.cap.read()
            self.step(frame if ok else None, time.time())
            if not self.handle_key(cv2.waitKeyEx(1 if ok else 30), time.time()):
                break
        self.cap.release()
        cv2.destroyAllWindows()


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))   # models/, calibration.json, sounds sit next to this file
    ap = argparse.ArgumentParser(description="Interactive UNO table")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--test", action="store_true", help="test mode (no projector)")
    g.add_argument("--projector", action="store_true", help="projector mode")
    ap.add_argument("--camera", help="camera index or DroidCam URL (overrides config)")
    ap.add_argument("--collect", metavar="LABEL",
                    help="save stable localized crops, including unknowns, to dataset/raw/LABEL (0-9 skip reverse draw2 wild wild4)")
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
