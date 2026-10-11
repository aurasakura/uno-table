"""
Game HUD on the projected board: each seat's name and card count near its own
table edge (facing that seat), a bar in the current colour along the edge of
the seat whose turn it is, and a circular arrow showing the play direction.
Kept small and dim so it never competes with the reactions. Stage.render paints
the discard zone and draw pile over it, so it can never cover them.
"""
import math

import cv2
import numpy as np

import config as C
from reactions import stamp_text

AA = cv2.LINE_AA


def edge_spots():
    """One spot per table side, same order and quarter turns as Reaction.around():
    (x, y, quarter_turns) for bottom, right, top, left."""
    B, m = C.BOARD_PX, C.HUD_EDGE_PX
    return [(B // 2, B - m, 0), (B - m, B // 2, 1), (B // 2, m, 2), (m, B // 2, 3)]


def edge_bar(board, side, colour):
    B, t = C.BOARD_PX, C.HUD_BAR_PX
    a, b = int(B * (1 - C.HUD_BAR_LEN_FRAC) / 2), int(B * (1 + C.HUD_BAR_LEN_FRAC) / 2)
    x0, y0, x1, y1 = [(a, B - t, b, B), (B - t, a, B, b), (a, 0, b, t), (0, a, t, b)][side]
    cv2.rectangle(board, (x0, y0), (x1 - 1, y1 - 1), colour, -1)


def direction_arrow(board, direction, colour):
    """Arc with an arrowhead: clockwise seen from above for +1 (P1 -> P2 -> P3 -> P4)."""
    B, r = C.BOARD_PX, C.HUD_ARROW_RADIUS
    cx, cy = int(C.HUD_ARROW_CENTER[0] * B), int(C.HUD_ARROW_CENTER[1] * B)
    a0, a1 = 30, 300
    cv2.ellipse(board, (cx, cy), (r, r), 0, a0, a1, colour, 3, AA)
    e = math.radians(a1 if direction > 0 else a0)
    tip = np.array([cx + r * math.cos(e), cy + r * math.sin(e)])
    tang = np.array([-math.sin(e), math.cos(e)]) * direction    # direction of travel at the tip
    norm = np.array([math.cos(e), math.sin(e)])
    pts = np.int32([tip + tang * 10, tip + norm * 8, tip - norm * 8])
    cv2.fillConvexPoly(board, pts, colour, AA)


def draw(board, snap, now=None):
    """Paint the HUD for Game.snapshot() `snap` onto the board image."""
    colour = C.DRAW_COLOURS.get(snap["colour"] or "wild", C.HUD_ACTIVE_BGR)
    spots = edge_spots()
    for seat, name in enumerate(snap["names"]):
        side = C.SEAT_SIDES[seat]
        x, y, q = spots[side]
        active = snap["winner"] is None and seat == snap["current"]
        text = f"{name}: {snap['hands'][seat]}"
        if snap["winner"] == seat:
            text, active = f"{name} WINS", True
        elif snap["pending_draw"] and snap["pending_draw"][0] == seat:
            text += f" (+{snap['pending_draw'][1]})"
        stamp_text(board, text, (x, y), q, C.HUD_ACTIVE_BGR if active else C.HUD_DIM_BGR,
                   C.HUD_TEXT_SCALE, C.HUD_TEXT_THICKNESS)
        if active:
            edge_bar(board, side, colour)
    direction_arrow(board, snap["direction"], colour)
    if now is not None:
        uno_prompt(board, snap, now)


def uno_prompt(board, snap, now):
    """Pulsing 'UNO?' facing the seat on 1 card, with a bar that shrinks as time runs out."""
    seat, left = snap["uno_seat"], snap["uno_left"]
    if seat is None or left is None:
        return
    side = C.SEAT_SIDES[seat]
    B, m = C.BOARD_PX, C.HUD_EDGE_PX + C.UNO_PROMPT_INSET_PX
    x, y, q = [(B // 2, B - m, 0), (B - m, B // 2, 1), (B // 2, m, 2), (m, B // 2, 3)][side]
    on = int(now * 4) % 2 == 0
    stamp_text(board, "UNO?", (x, y), q, (0, 0, 255) if on else (255, 255, 255), 1.1, 3)
    if C.UNO_WINDOW_SECONDS > 0:
        frac = left / C.UNO_WINDOW_SECONDS
        half = int(60 * frac)
        d = 26                                  # bar sits just outside the text, toward the table centre
        ends = [((x - half, y - d), (x + half, y - d)), ((x - d, y - half), (x - d, y + half)),
                ((x - half, y + d), (x + half, y + d)), ((x + d, y - half), (x + d, y + half))][side]
        cv2.line(board, *ends, (0, 0, 255), 4, AA)
