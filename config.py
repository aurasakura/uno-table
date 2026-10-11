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
CALIB_DOT_INSET = 0.10            # dots sit this far in from the square's corners (fraction)

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
