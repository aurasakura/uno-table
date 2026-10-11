"""
UNO call by showing a card back to the camera (no voice recognition).

The back of every UNO card is the same: a red oval with yellow 'UNO' letters on black.
While a seat is on 1 card (the UNO? countdown), main.py feeds each board image here; a
card back held up anywhere on the table for BACK_HOLD_SECONDS counts as the UNO call.
The discard zone and the draw pile (a stack of backs) are ignored.
"""
import cv2
import numpy as np

import config as C
from detector import colour_masks, detect_rect, draw_pile_rect


def _inside(x, y, rect):
    return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]


def find_back(board_bgr, projected=None):
    """Centre (x, y) of a card back on the board image, or None.
    projected: the board image the projector is showing right now. Pixels it lights up
    (effects, HUD) are ignored, so a projected red/yellow effect is never read as a card back."""
    m = colour_masks(board_bgr)
    if projected is not None:
        lit = cv2.dilate((projected.max(axis=2) > C.BACK_IGNORE_LIT_ABOVE).astype(np.uint8),
                         np.ones((9, 9), np.uint8)).astype(bool)
        for k in m:
            m[k] &= ~lit
    # The oval = red plus the yellow letters on it, closed into one solid shape.
    oval = cv2.morphologyEx((m["red"] | m["yellow"]).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, labels, stats, cents = cv2.connectedComponentsWithStats(oval)
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        cx, cy = cents[i]
        if area < C.BACK_MIN_RED_PX or _inside(cx, cy, detect_rect()) or _inside(cx, cy, draw_pile_rect()):
            continue
        box = (slice(y, y + h), slice(x, x + w))
        comp = labels[box] == i
        cs, _ = cv2.findContours(comp.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        c = max(cs, key=cv2.contourArea)
        if len(c) < 5:
            continue
        hull = cv2.contourArea(cv2.convexHull(c))
        (_, _), (ea, eb), _ = cv2.fitEllipse(c)
        ellipse = np.pi * ea * eb / 4
        # Shape: one solid oval (effects are thin rays, rings and sparks).
        if hull == 0 or ellipse == 0 or cv2.contourArea(c) / hull < C.BACK_MIN_SOLIDITY                 or not 0.75 <= hull / ellipse <= 1.3:
            continue
        red_share = m["red"][box][comp].mean()
        yellow_share = m["yellow"][box][comp].mean()
        if red_share < 0.4 or yellow_share < C.BACK_MIN_YELLOW:   # mostly red, with 'UNO' letters
            continue
        if (m["green"][box].mean() + m["blue"][box].mean()) > C.BACK_MAX_GREEN_BLUE:   # a wild card face
            continue
        return int(cx), int(cy)
    return None


class UnoCallWatcher:
    """True once a card back has been in view for BACK_HOLD_SECONDS."""

    def __init__(self):
        self.since = None

    def update(self, board_bgr, now, projected=None):
        if find_back(board_bgr, projected) is None:
            self.since = None
            return False
        if self.since is None:
            self.since = now
        if now - self.since >= C.BACK_HOLD_SECONDS:
            self.since = None
            return True
        return False
