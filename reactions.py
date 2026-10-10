"""
Reactions (animations) and the Stage that renders the board.

HOW TO ADD / CHANGE A REACTION
  1. Write a class that inherits Reaction and implements draw(self, layer, t):
       - layer: black board-sized image; draw with full colours (it is added onto the board)
       - t:     seconds since the reaction started
       - helpers: self.cx, self.cy (zone centre), self.r0 (radius just outside the zone),
                  self.colour (BGR of the card), self.k(t) (fade 1 -> 0 over duration)
  2. Put @reaction("key") above it. Keys: "red", "yellow", "green", "blue", "wild",
     and symbol keys "skip", "reverse", "draw2", "wild4" (or "7", "0", ... for numbers).
     A card's symbol reaction is used if one exists, otherwise its colour reaction.
  3. Set `duration` (seconds).
Anything drawn inside the discard zone is painted over with plain light (see Stage.render),
so the camera never mistakes an animation for a card.
"""
import math
import random

import cv2
import numpy as np

import config as C
from detector import zone_rect

REACTIONS = {}


def reaction(*keys):
    def register(cls):
        for k in keys:
            REACTIONS[k] = cls
        return cls
    return register


def scaled(bgr, k):
    return tuple(int(c * max(0.0, min(1.0, k))) for c in bgr)


AA = cv2.LINE_AA
RAINBOW = [C.DRAW_COLOURS[n] for n in ("red", "yellow", "green", "blue")]


class Reaction:
    duration = 2.0

    def __init__(self, card):
        self.card = card
        self.colour = C.DRAW_COLOURS.get(card.colour, (255, 255, 255))
        x0, y0, x1, y1 = zone_rect()
        self.cx, self.cy = (x0 + x1) // 2, (y0 + y1) // 2
        self.half_w, self.half_h = (x1 - x0) // 2, (y1 - y0) // 2
        self.r0 = int(math.hypot(self.half_w, self.half_h)) + C.ZONE_BORDER_PX
        self.setup()

    def setup(self):
        pass

    def k(self, t):
        return 1.0 - t / self.duration

    def draw(self, layer, t):
        raise NotImplementedError

    # Four positions around the zone, one facing each side of the table:
    # (x, y, counter-clockwise quarter turns so text reads upright for that player)
    def around(self, gap=70):
        return [(self.cx, self.cy + self.half_h + gap, 0), (self.cx + self.half_w + gap, self.cy, 1),
                (self.cx, self.cy - self.half_h - gap, 2), (self.cx - self.half_w - gap, self.cy, 3)]


def stamp_text(layer, text, centre, quarter_turns, colour, scale=2.5, thickness=6):
    """Draw text centred at `centre`, rotated so it faces one side of the table."""
    font = cv2.FONT_HERSHEY_DUPLEX
    (w, h), base = cv2.getTextSize(text, font, scale, thickness)
    patch = np.zeros((h + base + 10, w + 10, 3), np.uint8)
    cv2.putText(patch, text, (5, h + 5), font, scale, colour, thickness, AA)
    patch = np.rot90(patch, quarter_turns)
    ph, pw = patch.shape[:2]
    x, y = int(centre[0] - pw / 2), int(centre[1] - ph / 2)
    H, W = layer.shape[:2]
    xa, ya, xb, yb = max(x, 0), max(y, 0), min(x + pw, W), min(y + ph, H)
    if xa < xb and ya < yb:
        piece = np.ascontiguousarray(patch[ya - y:yb - y, xa - x:xb - x])
        layer[ya:yb, xa:xb] = cv2.add(layer[ya:yb, xa:xb], piece)


# =====================================================================
# Colour reactions
# =====================================================================
@reaction("blue")
class Ripple(Reaction):
    """Water ripples spreading out from the zone."""
    duration = 2.2

    def draw(self, layer, t):
        for i in range(5):
            tt = t - i * 0.25
            if tt < 0:
                continue
            k = 1 - tt / 1.5
            if k <= 0:
                continue
            r = int(self.r0 + tt * 220)
            cv2.circle(layer, (self.cx, self.cy), r, scaled(self.colour, k), max(2, int(12 * k)), AA)


@reaction("red")
class Burst(Reaction):
    """Fiery sparks shooting outwards."""
    duration = 1.6

    def setup(self):
        self.sparks = [(random.uniform(0, 2 * math.pi), random.uniform(120, 320), random.uniform(4, 10))
                       for _ in range(80)]

    def draw(self, layer, t):
        k = self.k(t)
        for ang, speed, size in self.sparks:
            d = self.r0 * 0.8 + speed * t
            x, y = int(self.cx + math.cos(ang) * d), int(self.cy + math.sin(ang) * d)
            hot = (0, int(160 * k), 255)          # orange -> red as it cools
            cv2.circle(layer, (x, y), max(1, int(size * k)), scaled(hot, k + 0.2), -1, AA)


@reaction("yellow")
class SunRays(Reaction):
    """Rotating rays of sunshine that grow and shrink."""
    duration = 1.8

    def draw(self, layer, t):
        grow = math.sin(math.pi * t / self.duration)
        spin = t * 1.2
        for i in range(18):
            a = spin + i * 2 * math.pi / 18
            r1, r2 = self.r0, self.r0 + 40 + 160 * grow
            p1 = (int(self.cx + math.cos(a) * r1), int(self.cy + math.sin(a) * r1))
            p2 = (int(self.cx + math.cos(a) * r2), int(self.cy + math.sin(a) * r2))
            cv2.line(layer, p1, p2, scaled(self.colour, grow + 0.1), 7, AA)
        cv2.circle(layer, (self.cx, self.cy), self.r0 + 5, scaled(self.colour, grow), 10, AA)


@reaction("green")
class Spiral(Reaction):
    """Three vines of dots spiralling outwards."""
    duration = 2.0

    def draw(self, layer, t):
        k = min(1.0, 2.5 * self.k(t))          # stay bright, fade at the end
        steps = int(60 * min(1.0, t / (self.duration * 0.6)))
        for arm in range(3):
            for j in range(steps):
                a = j * 0.18 + arm * 2 * math.pi / 3 + t * 0.8
                r = self.r0 * 0.7 + j * 4.5
                x, y = int(self.cx + math.cos(a) * r), int(self.cy + math.sin(a) * r)
                cv2.circle(layer, (x, y), 3 + j // 12, scaled(self.colour, k), -1, AA)


@reaction("wild")
class Pinwheel(Reaction):
    """Four-colour pinwheel spinning around the zone plus rainbow rings."""
    duration = 2.5

    def draw(self, layer, t):
        k = min(1.0, 2.0 * self.k(t))
        r = int(self.r0 + 40 + 120 * min(1.0, t / 0.6))
        spin = t * 220                           # degrees
        for i, col in enumerate(RAINBOW):
            for half in (0, 180):                # 8 blades: each colour twice
                start = spin + i * 45 + half
                cv2.ellipse(layer, (self.cx, self.cy), (r, r), 0, start, start + 30, scaled(col, k), -1, AA)
        for i, col in enumerate(RAINBOW):
            tt = t - i * 0.2
            if tt > 0:
                cv2.circle(layer, (self.cx, self.cy), int(r + 20 + tt * 150),
                           scaled(col, k * (1 - tt / 2.3)), 6, AA)


# =====================================================================
# Action reactions (used once recognise_symbol() returns a symbol,
# or with the fake-card keys 1-4)
# =====================================================================
@reaction("skip")
class Skip(Ripple):
    """Ripple + a pulsing 'no entry' sign facing every player."""
    duration = 2.2

    def draw(self, layer, t):
        super().draw(layer, t)
        k = self.k(t)
        r = int(38 + 6 * math.sin(t * 12))
        for x, y, _ in self.around():
            cv2.circle(layer, (x, y), r, scaled(self.colour, k), 8, AA)
            d = int(r * 0.7)
            cv2.line(layer, (x - d, y + d), (x + d, y - d), scaled(self.colour, k), 8, AA)


@reaction("reverse")
class Reverse(Ripple):
    """Ripple + spinning pairs of arrows."""
    duration = 2.2

    def draw(self, layer, t):
        super().draw(layer, t)
        col = scaled(self.colour, self.k(t))
        r = 36
        for x, y, _ in self.around():
            for base in (0, 180):
                a0 = math.degrees(t * 4) + base
                a1 = a0 + 140
                cv2.ellipse(layer, (x, y), (r, r), 0, a0, a1, col, 7, AA)
                e = math.radians(a1)
                tip = (x + r * math.cos(e), y + r * math.sin(e))
                tang = (-math.sin(e), math.cos(e))           # direction of travel
                norm = (math.cos(e), math.sin(e))
                pts = np.int32([[tip[0] + tang[0] * 14, tip[1] + tang[1] * 14],
                                [tip[0] + norm[0] * 12, tip[1] + norm[1] * 12],
                                [tip[0] - norm[0] * 12, tip[1] - norm[1] * 12]])
                cv2.fillConvexPoly(layer, pts, col, AA)


@reaction("draw2")
class DrawTwo(Burst):
    """Sparks + '+2' facing every player."""
    duration = 2.0

    def draw(self, layer, t):
        super().draw(layer, t)
        k = self.k(t)
        pop = min(1.0, t / 0.25)
        for x, y, q in self.around(75):
            stamp_text(layer, "+2", (x, y), q, scaled(self.colour, k + 0.2), 1.0 + 1.2 * pop, 5)


@reaction("wild4")
class WildFour(Pinwheel):
    """Pinwheel + '+4' in white facing every player."""
    duration = 2.8

    def draw(self, layer, t):
        super().draw(layer, t)
        pop = min(1.0, t / 0.25)
        for x, y, q in self.around(75):
            stamp_text(layer, "+4", (x, y), q, scaled((255, 255, 255), self.k(t) + 0.2), 1.0 + 1.2 * pop, 5)


# =====================================================================
# Stage: keeps the running reactions and renders the board image
# =====================================================================
class Stage:
    def __init__(self):
        self.active = []          # list of (reaction, start_time)
        self.last_card = None

    def trigger(self, card, now):
        cls = REACTIONS.get(card.symbol) or REACTIONS.get(card.colour)
        if cls is None:
            print(f"[reactions] no reaction registered for {card}")
            return
        self.active.append((cls(card), now))
        self.last_card = card
        print(f"[reactions] {card} -> {cls.__name__}")

    def render(self, now):
        B = C.BOARD_PX
        board = np.full((B, B, 3), C.BACKGROUND_BGR, np.uint8)
        layer = np.zeros_like(board)
        still_running = []
        for r, start in self.active:
            t = (now - start) * C.REACTION_SPEED
            if t < r.duration:
                r.draw(layer, t)
                still_running.append((r, start))
        self.active = still_running
        board = cv2.add(board, layer)

        # Discard zone: border just outside, then plain steady light inside (always on top).
        x0, y0, x1, y1 = zone_rect()
        b = C.ZONE_BORDER_PX
        cv2.rectangle(board, (x0 - b, y0 - b), (x1 + b - 1, y1 + b - 1), C.ZONE_BORDER_BGR, -1)
        board[y0:y1, x0:x1] = C.ZONE_FILL_BGR
        return board
