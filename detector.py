"""
Card detection in the discard zone.

Pipeline (CardDetector.update, called once per camera frame with the top-down board image):
  1. crop the discard zone
  2. wait until it has been still for STILL_SECONDS (a passing hand keeps resetting the timer)
  3. compare with the zone as it looked at the last read; ignore if it hasn't changed
  4. locate a card against the empty zone and straighten its crop
  5. require compatible colour AND symbol evidence before emitting a play
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
    fake: bool = False              # entered with a key: the symbol is known even when None

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


def draw_pile_rect():
    """(x0, y0, x1, y1) of the face-down draw pile. The detector never looks here."""
    B = C.BOARD_PX
    cx, cy = C.DRAW_PILE_CENTER[0] * B, C.DRAW_PILE_CENTER[1] * B
    hw, hh = C.DRAW_PILE_W_FRAC * B / 2, C.DRAW_PILE_H_FRAC * B / 2
    return int(cx - hw), int(cy - hh), int(cx + hw), int(cy + hh)


def corner_keepouts():
    """(x0, y0, x1, y1) of the four corner squares (post + margin) where nothing may be projected."""
    B = C.BOARD_PX
    s = round((C.CORNER_POST_CM + C.CORNER_MARGIN_CM) * B / C.TABLE_CM)
    return [(0, 0, s, s), (B - s, 0, B, s), (B - s, B - s, B, B), (0, B - s, s, B)]


def hits_keepout(x0, y0, x1, y1):
    """True if the rectangle overlaps any corner keep-out square."""
    return any(x0 < kx1 and kx0 < x1 and y0 < ky1 and ky0 < y1
               for kx0, ky0, kx1, ky1 in corner_keepouts())


def circle_hits_keepout(x, y, r):
    """True if a circle (board px) touches any corner keep-out square."""
    for kx0, ky0, kx1, ky1 in corner_keepouts():
        nx, ny = min(max(x, kx0), kx1), min(max(y, ky0), ky1)    # nearest point of the square
        if (x - nx) ** 2 + (y - ny) ** 2 < r * r:
            return True
    return False


def detect_rect():
    """The part of the zone that is actually analysed (zone shrunk by ZONE_INSET_PX)."""
    x0, y0, x1, y1 = zone_rect()
    i = C.ZONE_INSET_PX
    return x0 + i, y0 + i, x1 - i, y1 - i


# ---------------------------------------------------------------------
# Colour classification
# ---------------------------------------------------------------------
def colour_masks(bgr, val_min=None):
    """Boolean masks per colour name (+ 'black') for an image."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    coloured = (s >= C.SAT_MIN) & (v >= (C.VAL_MIN if val_min is None else val_min))
    masks = {}
    for name, ranges in C.HUE_RANGES.items():
        m = np.zeros(h.shape, bool)
        for lo, hi in ranges:
            m |= (h >= lo) & (h <= hi)
        masks[name] = m & coloured
    masks["black"] = v <= C.BLACK_VAL_MAX
    return masks


def classify_colour(bgr):
    """Dominant supported card hue; darkness never identifies a wild card."""
    masks = colour_masks(bgr, val_min=C.CARD_VAL_MIN)
    fr = {name: float(m.mean()) for name, m in masks.items()}
    best, second = sorted(COLOURS, key=lambda n: fr[n], reverse=True)[:2]
    supported = fr[best] >= C.MIN_COLOUR_FRACTION
    ambiguous = fr[second] >= C.COLOUR_SECOND_MIN and fr[second] >= fr[best] * C.COLOUR_SECOND_RATIO
    label = best if supported and not ambiguous else None
    card_mask = np.zeros(bgr.shape[:2], bool)
    for name in COLOURS:
        card_mask |= masks[name]
    return label, fr, card_mask


def classify_hsv_pixel(h, s, v):
    """Which class a single HSV pixel falls into (used by the debug click)."""
    if s < C.SAT_MIN or v < C.CARD_VAL_MIN:
        return "black (not a card identity)" if v <= C.BLACK_VAL_MAX else "none (not saturated/bright enough)"
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
    centre = pts.mean(axis=0)
    angles = np.arctan2(pts[:, 1] - centre[1], pts[:, 0] - centre[0])
    ordered = pts[np.argsort(angles)]
    # Sum/difference corner selection repeats a point on 45-degree rectangles.
    return np.roll(ordered, -int(ordered.sum(1).argmin()), axis=0).astype(np.float32)


def extract_card_image(zone_bgr, card_mask, size=(200, 300)):
    """Cut the card out of the zone and straighten it to an upright (portrait) image.
    Returns None without a plausible outline; never classifies the whole zone."""
    m = cv2.morphologyEx(card_mask.astype(np.uint8) * 255, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in sorted(contours, key=cv2.contourArea, reverse=True):
        rect = cv2.minAreaRect(c)
        a, b = sorted(rect[1])
        area = a * b
        if (a > 0 and 0.03 * m.size <= area <= 0.85 * m.size
                and 1.15 <= b / a <= 2.15 and cv2.contourArea(c) >= 0.55 * area):
            break
    else:
        return None
    box = _order_points(cv2.boxPoints(rect))
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
    detected_colour, symbol, _ = yolo_symbol.recognise(board_bgr, zone)
    if symbol not in ("wild", "wild4") and detected_colour != colour:
        return None
    return symbol


REGULAR_SYMBOLS = tuple(str(n) for n in range(10)) + ("skip", "reverse", "draw2")


def recognise_card(card_bgr, board_bgr=None, zone=None):
    """Joint recognition of a localized crop. None means do not advance play."""
    colour, fractions, _ = classify_colour(card_bgr)
    symbol = recognise_symbol(card_bgr, colour, board_bgr, zone)
    if symbol in ("wild", "wild4"):
        # The symbol identifies a wild. Multiple hues reject a conflicting regular
        # face; black/shadow alone never supplies either piece of evidence.
        if sum(fractions[c] >= C.WILD_MIN_COLOUR_FRACTION for c in COLOURS) < C.WILD_MIN_COLOURS:
            return None
        return Card("wild", symbol, fractions)
    if colour in COLOURS and symbol in REGULAR_SYMBOLS:
        return Card(colour, symbol, fractions)
    return None


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
        self.empty_zone = None     # localization always compares with the empty table
        self.still_since = 0.0
        self.last_read_time = 0.0
        self.status = "waiting"
        self.motion = 0.0
        self.change = 0.0
        self.fractions = {}
        self.live_label = None
        self.last_card_img = None   # straightened crop of the last read card (for --collect)
        self.capture_ready = False
        self.capture_baseline = None
        self.last_capture_time = 0.0

    def update(self, board_bgr, now, collect=False):
        """Feed one top-down board image. Returns a Card when a new card is read, else None."""
        x0, y0, x1, y1 = detect_rect()
        zone = board_bgr[y0:y1, x0:x1]
        small = _small(zone)
        self.capture_ready = False
        self.live_label, self.fractions = None, {}

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
            self.empty_zone = zone.copy()
            self.status = "learned empty zone"
            return None
        self.change = _diff_fraction(small, self.baseline)
        if self.change < C.CHANGE_MIN_FRACTION:
            self.status = "still, same as last read"
            return None
        if now - self.last_read_time < C.READ_COOLDOWN_SECONDS:
            self.status = "cooldown"
            return None
        # Hue/black masks merge projector tint and shadows into the card. Use the
        # actual empty zone and require an outline before any model read.
        mask = cv2.absdiff(zone, self.empty_zone).max(axis=2) > C.MOTION_PIXEL_DIFF
        card_img = extract_card_image(zone, mask)
        if card_img is None:
            self.last_card_img = None
            self.status = "waiting: no clear card outline"
            return None
        self.last_card_img = card_img
        self.live_label, self.fractions, _ = classify_colour(card_img)
        if collect and (self.capture_baseline is None or
                        _diff_fraction(small, self.capture_baseline) >= C.CHANGE_MIN_FRACTION):
            if now - self.last_capture_time >= C.READ_COOLDOWN_SECONDS:
                self.capture_ready = True
                self.capture_baseline = small.copy()
                self.last_capture_time = now
        card = recognise_card(card_img, board_bgr, (x0, y0, x1, y1))
        if card is None:
            self.status = "waiting: colour/symbol unknown or conflicting"
            return None
        self.baseline = small
        self.last_read_time = now
        self.live_label = card.colour
        self.status = f"READ {card}"
        return card
