"""
All settings for the UNO table live here.
Change values in this file; nothing else should need editing for tuning.
"""

# =====================================================================
# MODE
# =====================================================================
# True  = laptop + phone only (projector output shown in a normal window)
# False = real projector under the table (mirroring, fullscreen, dot calibration)
# Can be overridden on the command line:  python main.py --projector  /  --test
TEST_MODE = True

# =====================================================================
# CAMERA (phone via DroidCam)
# =====================================================================
# Webcam index (try 0, 1, 2 ... run `python main.py --probe` to see them all),
# or a DroidCam URL string such as "http://192.168.1.23:4747/video".
CAMERA_INDEX = 0
# Windows capture backend for numeric indexes: "dshow" (usually best for DroidCam), "msmf" or "any"
CAMERA_BACKEND = "dshow"
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720

# =====================================================================
# BOARD (the virtual top-down square = the whole play area)
# =====================================================================
BOARD_PX = 600                    # board image is BOARD_PX x BOARD_PX pixels
TABLE_CM = 50                     # the board maps to the whole 50 x 50 cm acrylic top
CORNER_POST_CM = 4                # a 4 x 4 cm post at each corner blocks the projection there
CORNER_MARGIN_CM = 1              # extra safety around each post; nothing is projected in post + margin

# =====================================================================
# DISCARD ZONE (fractions of the board, centred at ZONE_CENTER)
# =====================================================================
ZONE_CENTER = (0.5, 0.5)          # (x, y) as fractions of the board
ZONE_W_FRAC = 0.28                # 0.28 * 50 cm = 14 cm wide
ZONE_H_FRAC = 0.34                # 0.34 * 50 cm = 17 cm tall
ZONE_INSET_PX = 8                 # detection ignores this many px at the zone edge
ZONE_FILL_BGR = (220, 220, 220)   # steady plain light projected inside the zone
ZONE_BORDER_BGR = (90, 90, 90)    # outline drawn just OUTSIDE the zone
ZONE_BORDER_PX = 6
BACKGROUND_BGR = (0, 0, 0)        # board background (black = no projector light)

# =====================================================================
# DRAW PILE (face-down cards; fractions of the board, like the discard zone)
# =====================================================================
# Painted with plain steady light, never with effects or HUD. The detector never looks here.
DRAW_PILE_CENTER = (0.78, 0.22)   # top-right of the discard zone, between the top and right seats
DRAW_PILE_W_FRAC = 0.16           # 8 cm wide
DRAW_PILE_H_FRAC = 0.22           # 11 cm tall
DRAW_PILE_FILL_BGR = (150, 150, 150)
DRAW_PILE_BORDER_BGR = (90, 90, 90)
DRAW_PILE_BORDER_PX = 3

# =====================================================================
# CARD DETECTION
# =====================================================================
DETECT_PX = 96                    # zone is shrunk to this size for motion/change checks
MOTION_PIXEL_DIFF = 25            # a pixel "changed" if any channel differs by more than this
STILL_MAX_FRACTION = 0.01         # zone is "still" if fewer than 1% of pixels moved
STILL_SECONDS = 0.6               # zone must be still this long before a card is read
CHANGE_MIN_FRACTION = 0.06        # zone must differ >6% from the last read to count as a new card
READ_COOLDOWN_SECONDS = 1.0       # minimum time between two card reads

# Colour classification, OpenCV HSV: H 0-179, S 0-255, V 0-255
SAT_MIN = 90                      # pixels less saturated than this are "not coloured" (white, grey, skin)
VAL_MIN = 60                      # pixels darker than this are not counted as coloured
BLACK_VAL_MAX = 60                # pixels darker than this count as "black" (wild)
HUE_RANGES = {
    "red":    [(0, 8), (170, 179)],
    "yellow": [(18, 35)],
    "green":  [(40, 85)],
    "blue":   [(90, 130)],
}
MIN_COLOUR_FRACTION = 0.08        # this share of the zone must be one colour to read a card
MIN_BLACK_FRACTION = 0.10         # this share of the zone must be black to read a wild

# =====================================================================
# REACTIONS
# =====================================================================
# Colours used when drawing reactions (BGR)
DRAW_COLOURS = {
    "red":    (40, 40, 255),
    "yellow": (0, 220, 255),
    "green":  (60, 220, 60),
    "blue":   (255, 140, 30),
    "wild":   (255, 255, 255),
}
REACTION_SPEED = 1.0              # >1 = faster animations, <1 = slower

# =====================================================================
# PROJECTOR
# =====================================================================
PROJECTOR_WIDTH = 1280            # projector native resolution
PROJECTOR_HEIGHT = 720
PROJECTOR_SCREEN_X = 1920         # where the projector screen starts on the desktop
PROJECTOR_SCREEN_Y = 0            # (usually = laptop screen width, 0)
PROJECTOR_START_FULLSCREEN = True
DEFAULT_MIRROR = True             # rear projection: mirror the image
DEFAULT_ROTATE = 0                # 0-3, quarter turns clockwise
MOVE_STEP_PX = 10                 # arrow-key move step
RESIZE_STEP_PX = 10               # +/- resize step
CALIB_DOT_RADIUS = 18             # size of projected calibration dots
CALIB_DOT_INSET = 0.15            # dots sit this far in from the square's corners (fraction);
                                  # 0.15 = 7.5 cm, so the whole dot is clear of the corner posts

# =====================================================================
# WINDOWS / FILES
# =====================================================================
TEST_PROJECTOR_WINDOW_PX = 600    # size of the fake projector window in test mode
CALIBRATION_FILE = "calibration.json"

# =====================================================================
# SYMBOL RECOGNITION (YOLOv8, optional)
# =====================================================================
# Reads numbers / skip / reverse / +2 / +4 on the cut-out card. Needs `pip install ultralytics`.
# If the model or ultralytics is missing, cards are read by colour only.
YOLO_ENABLED = True
YOLO_MODEL = "models/best_train2.pt"
YOLO_CONF = 0.4
# Our own classifier for the real deck (made by train_symbols.py). Used instead of the
# pretrained detector once this file exists.
SYMBOL_MODEL = "models/symbols.pt"
SYMBOL_CONF = 0.6

# =====================================================================
# GAME RULES (game.py, see rules.md)
# =====================================================================
SEAT_NAMES = ("P1", "P2", "P3", "P4")   # in turn order (clockwise seen from above = "to the left")
# Which side of the table each seat sits on: 0 bottom, 1 right, 2 top, 3 left
# (same order as Reaction.around()). P1 bottom, P2 on P1's left, and so on.
SEAT_SIDES = (0, 3, 2, 1)
START_HAND = 7                    # cards dealt to each player
FIRST_SEAT = 0                    # P1 plays first (the dealer is the seat before it)
REJECT_ILLEGAL = False            # False = warn but still record an illegal card (keeps the game in sync)
                                  # True  = refuse it: the player takes it back, nothing changes
UNO_PENALTY = True                # forgot to call UNO before the next player acted -> draw cards
UNO_PENALTY_CARDS = 2
UNO_WINDOW_SECONDS = 4.0          # time to press U after going down to 1 card (0 = until the next player acts)

# =====================================================================
# HUD (turn / card counts / direction / colour, projected near the table edges)
# =====================================================================
HUD_EDGE_PX = 28                  # seat labels sit this far in from each board edge
HUD_TEXT_SCALE = 0.7
HUD_TEXT_THICKNESS = 2
HUD_DIM_BGR = (90, 90, 90)        # seats that are waiting
HUD_ACTIVE_BGR = (255, 255, 255)  # seat whose turn it is
HUD_BAR_PX = 6                    # bar along the active seat's edge, in the current colour
HUD_BAR_LEN_FRAC = 0.36
HUD_ARROW_CENTER = (0.20, 0.80)   # direction arrow: bottom-left, clear of the corner post and seat labels
HUD_ARROW_RADIUS = 24
UNO_PROMPT_INSET_PX = 45         # "UNO?" prompt sits this far inside the seat label

# =====================================================================
# UNO CALL BY CARD BACK (uno_call.py)
# =====================================================================
# During the UNO? countdown, holding a card back up to the camera calls UNO (U still works).
UNO_CALL_BY_CARD_BACK = True
BACK_HOLD_SECONDS = 0.4           # back must stay in view this long (stops one-frame flickers)
BACK_MIN_RED_PX = 800             # smallest red oval, in board pixels (board is BOARD_PX square)
BACK_MIN_YELLOW = 0.04            # share of the oval that is yellow ('UNO' letters)
BACK_MIN_SOLIDITY = 0.85          # oval area / its convex hull: a solid oval, not rays or sparks
BACK_MAX_GREEN_BLUE = 0.05        # more green/blue than this = a wild card face, not a back
BACK_IGNORE_LIT_ABOVE = 60        # camera ignores pixels the projector lights brighter than this

# =====================================================================
# SOUND (sound.py, spec in sound_mapping.md)
# =====================================================================
# Needs `pip install pygame-ce`. Without it (or without an audio device) the app runs silently.
SOUND_ENABLED = True
SOUND_VOLUME = 0.8                # 0..1, applies to every sound
SOUND_DIR = "sound_effects"
SOUND_STACK_STEP = 2              # +2 on +2: semitones higher per stacked card (row 11)
# key -> recipe. A recipe is a file name, or an op tuple (see the top of sound.py):
#   ("pitch", r, semitones) ("reverse", r) ("gain", r, g) ("trim", r)
#   ("layer", r1, r2, ...)  ("seq", r, times, gap_s)  ("chain", gap_s, r1, r2, ...)
CHIME = {"red": 0, "yellow": 4, "green": 9, "blue": 7}   # semitones above correct.wav (C)
SOUND_MAP = {
    "start":   "drum.mp3",                                        # 1  key N / first card
    **{c: ("pitch", "correct.wav", s) for c, s in CHIME.items()}, # 3  number card (and 9: colour after a wild)
    **{f"change_{c}": ("layer", ("pitch", "correct.wav", s), ("trim", ("gain", "swish.mp3", 8)))
       for c, s in CHIME.items()},                                # 4  same number, new colour
    "skip":    ("layer", "bonk.mp3", ("gain", "buzzer.wav", 0.5)),               # 5
    "reverse": ("reverse", ("trim", ("gain", "swish.mp3", 10))),   # swish peaks at 5%: boost                          # 6
    "draw2":   ("seq", "thud.wav", 2, 0.25),                      # 7
    "wild":    ("chain", 0.1, *[("pitch", "correct.wav", s) for s in (0, 4, 7, 9, 12)]),   # 8
    "wild4":   "explosion.wav",                                   # 10
    "draw2_stack": "thud.wav",                                    # 11 pitched up SOUND_STACK_STEP per stack
    "turn":    ("gain", ("trim", "tick.mp3"), 0.5),            # trim: tick.mp3 starts with 1.25 s of silence                         # 12 after every valid card
    "draw":    "card_flick.mp3",                                  # 13 key D
    "illegal": ("gain", ("pitch", "buzzer.wav", -5), 0.5),                       # 14 card breaks the rules
    "uno":     ("seq", "alarm.wav", 3, 0.35),                     # 15 key U or card back held up
    "forgot_uno": "sad_trombone.wav",                             # 16 automatic UNO penalty
    "win":     "cheer.wav",                                       # 17 last card / key V
    "uno_due": ("gain", ("seq", ("trim", "tick.mp3"), 2, 0.3), 0.4),   # our addition: UNO? countdown starts
}
