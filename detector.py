"""
Card detection in the discard zone.

Pipeline (CardDetector.update, called once per camera frame with the top-down board image):
  1. crop the discard zone
  2. wait until it has been still for STILL_SECONDS (a passing hand keeps resetting the timer)
  3. compare with the zone as it looked at the last read; ignore if it hasn't changed
  4. classify the colour (red / yellow / green / blue / wild)
  5. cut out the card and call recognise_symbol()   <-- add number/action recognition there
"""
from dataclasses import dataclass, field

import cv2
import numpy as np

import config as C

COLOURS = ("red", "yellow", "green", "blue")


@dataclass
class Card:
    colour: str                     # "red" | "yellow" | "green" | "blue" | "wild"
    symbol: str | None = None       # "0".."9", "skip", "reverse", "draw2", "wild4", or None if unknown
    scores: dict = field(default_factory=dict)

    def __str__(self):
        return self.colour if self.symbol is None else f"{self.colour} {self.symbol}"


# ---------------------------------------------------------------------
# Zone geometry (board pixel coordinates)
# ---------------------------------------------------------------------
def zone_rect():
    """(x0, y0, x1, y1) of the discard zone on the board."""
    B = C.BOARD_PX
    cx, cy = C.ZONE_CENTER[0] * B, C.ZONE_CENTER[1] * B
    hw, hh = C.ZONE_W_FRAC * B / 2, C.ZONE_H_FRAC * B / 2
    return int(cx - hw), int(cy - hh), int(cx + hw), int(cy + hh)


def detect_rect():
    """The part of the zone that is actually analysed (zone shrunk by ZONE_INSET_PX)."""
    x0, y0, x1, y1 = zone_rect()
    i = C.ZONE_INSET_PX
    return x0 + i, y0 + i, x1 - i, y1 - i


# ---------------------------------------------------------------------
# Colour classification
# ---------------------------------------------------------------------
def colour_masks(bgr):
    """Boolean masks per colour name (+ 'black') for an image."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    coloured = (s >= C.SAT_MIN) & (v >= C.VAL_MIN)
    masks = {}
    for name, ranges in C.HUE_RANGES.items():
        m = np.zeros(h.shape, bool)
        for lo, hi in ranges:
            m |= (h >= lo) & (h <= hi)
        masks[name] = m & coloured
    masks["black"] = v <= C.BLACK_VAL_MAX
    return masks


def classify_colour(bgr):
    """Return (label or None, fractions dict, card mask) for a zone image."""
    masks = colour_masks(bgr)
    fr = {name: float(m.mean()) for name, m in masks.items()}
    best = max(COLOURS, key=lambda n: fr[n])
    if fr["black"] >= C.MIN_BLACK_FRACTION and fr["black"] >= fr[best]:
        label = "wild"
    elif fr[best] >= C.MIN_COLOUR_FRACTION:
        label = best
    else:
        label = None
    card_mask = np.zeros(bgr.shape[:2], bool)
    for m in masks.values():
        card_mask |= m
    return label, fr, card_mask


def classify_hsv_pixel(h, s, v):
    """Which class a single HSV pixel falls into (used by the debug click)."""
    if v <= C.BLACK_VAL_MAX:
        return "black"
    if s < C.SAT_MIN or v < C.VAL_MIN:
        return "none (not saturated/bright enough)"
    for name, ranges in C.HUE_RANGES.items():
        if any(lo <= h <= hi for lo, hi in ranges):
            return name
    return "none (hue outside all ranges)"


# ---------------------------------------------------------------------
# Card cut-out + symbol recognition hook
# ---------------------------------------------------------------------
def _order_points(pts):
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    pts = np.asarray(pts, np.float32)
    s, d = pts.sum(1), np.diff(pts, axis=1).ravel()
    return np.array([pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]], np.float32)


def extract_card_image(zone_bgr, card_mask, size=(200, 300)):
    """Cut the card out of the zone and straighten it to an upright (portrait) image.
    Falls back to the whole zone if no clear card outline is found."""
    m = cv2.morphologyEx(card_mask.astype(np.uint8) * 255, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return zone_bgr
    c = max(contours, key=cv2.contourArea)
    if cv2.contourArea(c) < 0.03 * m.size:
        return zone_bgr
    box = _order_points(cv2.boxPoints(cv2.minAreaRect(c)))
    tl, tr, br, bl = box
    if np.linalg.norm(tr - tl) > np.linalg.norm(br - tr):   # landscape -> turn to portrait
        box = np.array([tr, br, bl, tl], np.float32)
    w, h = size
    dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], np.float32)
    return cv2.warpPerspective(zone_bgr, cv2.getPerspectiveTransform(box, dst), (w, h))


def recognise_symbol(card_bgr, colour, board_bgr=None, zone=None):
    """
    >>> HOOK: number / action-card recognition goes here. <<<

    card_bgr: the card cut out and straightened (portrait, ~200x300 px), or the whole zone
              if the outline wasn't found.
    colour:   the colour already detected ("red", ..., "wild").

    Return one of "0".."9", "skip", "reverse", "draw2", "wild4", or None if unknown.
    Returning e.g. "skip" automatically plays the "skip" reaction (see reactions.py).

    Ideas for later:
      - threshold the white oval in the middle, take the symbol inside it and
        template-match against one reference image per symbol (cv2.matchTemplate),
      - or count holes / contour shapes of the symbol,
      - or train a tiny classifier on saved crops (save card_bgr with cv2.imwrite to collect data).
    Remember the symbol can be upside down; try the image and its 180-degree rotation.
    """
    # YOLO needs the wider scene (it misses tight card crops), so read the whole
    # board and keep the detection centred in the discard zone.
    import yolo_symbol
    if yolo_symbol.has_classifier():          # our own trained model (train_symbols.py)
        return yolo_symbol.classify(card_bgr)
    if board_bgr is None:
        return None
    _, symbol, _ = yolo_symbol.recognise(board_bgr, zone)
    return symbol


# ---------------------------------------------------------------------
# The detector state machine
# ---------------------------------------------------------------------
def _diff_fraction(a, b):
    return float((cv2.absdiff(a, b).max(axis=2) > C.MOTION_PIXEL_DIFF).mean())


def _small(zone_bgr):
    s = cv2.resize(zone_bgr, (C.DETECT_PX, C.DETECT_PX), interpolation=cv2.INTER_AREA)
    return cv2.GaussianBlur(s, (5, 5), 0)


class CardDetector:
    def __init__(self):
        self.reset()

    def reset(self):
        """Forget everything; the next still zone becomes the 'empty' baseline."""
        self.prev = None
        self.baseline = None       # zone as it looked at the last read (or when empty)
        self.still_since = 0.0
        self.last_read_time = 0.0
        self.status = "waiting"
        self.motion = 0.0
        self.change = 0.0
        self.fractions = {}
        self.live_label = None
        self.last_card_img = None   # straightened crop of the last read card (for --collect)

    def update(self, board_bgr, now):
        """Feed one top-down board image. Returns a Card when a new card is read, else None."""
        x0, y0, x1, y1 = detect_rect()
        zone = board_bgr[y0:y1, x0:x1]
        small = _small(zone)
        self.live_label, self.fractions, _ = classify_colour(
            cv2.resize(zone, (128, 128), interpolation=cv2.INTER_AREA))

        if self.prev is None:
            self.prev, self.still_since = small, now
            return None
        self.motion = _diff_fraction(small, self.prev)
        self.prev = small
        if self.motion > C.STILL_MAX_FRACTION:
            self.still_since = now
            self.status = "moving"
            return None
        still_for = now - self.still_since
        if still_for < C.STILL_SECONDS:
            self.status = f"settling {still_for:.1f}s"
            return None

        if self.baseline is None:
            self.baseline = small
            self.status = "learned empty zone"
            return None
        self.change = _diff_fraction(small, self.baseline)
        if self.change < C.CHANGE_MIN_FRACTION:
            self.status = "still, same as last read"
            return None
        if now - self.last_read_time < C.READ_COOLDOWN_SECONDS:
            self.status = "cooldown"
            return None
        if self.live_label is None:
            # Changed but no card colour (card removed, hand resting, lighting shift).
            # Keep the old baseline so the same card isn't re-read when the hand leaves.
            self.status = "changed, no card colour"
            return None

        # New card!
        self.baseline = small
        self.last_read_time = now
        _, _, mask_full = classify_colour(zone)
        card_img = extract_card_image(zone, mask_full)
        self.last_card_img = card_img
        card = Card(self.live_label, recognise_symbol(card_img, self.live_label, board_bgr, (x0, y0, x1, y1)), dict(self.fractions))
        self.status = f"READ {card}"
        return card
