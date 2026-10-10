"""
Where the board square lands in the projector image: position, size, rotation, mirror.
The whole transform is one 3x3 matrix (board px -> projector px), so the same matrix is used
to draw the output AND to line the camera up with the board after calibration.
"""
import cv2
import numpy as np

import config as C


class Placement:
    def __init__(self, size=None, offset=None, rotate=C.DEFAULT_ROTATE, mirror=C.DEFAULT_MIRROR):
        pw, ph = C.PROJECTOR_WIDTH, C.PROJECTOR_HEIGHT
        self.size = int(size or min(pw, ph) * 0.9)
        self.offset = list(offset) if offset else [(pw - self.size) // 2, (ph - self.size) // 2]
        self.rotate = int(rotate) % 4
        self.mirror = bool(mirror)

    # --- keyboard adjustments ---
    def move(self, dx, dy):
        self.offset[0] += dx * C.MOVE_STEP_PX
        self.offset[1] += dy * C.MOVE_STEP_PX

    def resize(self, steps):
        new = max(100, self.size + steps * C.RESIZE_STEP_PX)
        d = (new - self.size) / 2          # keep the square centred while resizing
        self.offset = [int(self.offset[0] - d), int(self.offset[1] - d)]
        self.size = new

    def rotate_cw(self):
        self.rotate = (self.rotate + 1) % 4

    def toggle_mirror(self):
        self.mirror = not self.mirror

    # --- maths ---
    def matrix(self):
        """3x3 matrix mapping board pixels -> projector pixels."""
        half = C.BOARD_PX / 2
        to_centre = np.array([[1, 0, -half], [0, 1, -half], [0, 0, 1]], float)
        mirror = np.diag([-1.0 if self.mirror else 1.0, 1.0, 1.0])
        c, s = [(1, 0), (0, 1), (-1, 0), (0, -1)][self.rotate]
        rot = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], float)
        k = self.size / C.BOARD_PX
        scale = np.diag([k, k, 1.0])
        place = np.array([[1, 0, self.offset[0] + self.size / 2],
                          [0, 1, self.offset[1] + self.size / 2], [0, 0, 1]], float)
        return place @ scale @ rot @ mirror @ to_centre

    def board_to_projector(self, pts):
        pts = np.asarray(pts, np.float32).reshape(-1, 1, 2)
        return cv2.perspectiveTransform(pts, self.matrix()).reshape(-1, 2)

    def render(self, board):
        """Board image -> full projector frame."""
        return cv2.warpAffine(board, self.matrix()[:2], (C.PROJECTOR_WIDTH, C.PROJECTOR_HEIGHT),
                              flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))

    # --- save / load ---
    def to_dict(self):
        return {"size": self.size, "offset": self.offset, "rotate": self.rotate, "mirror": self.mirror}

    @classmethod
    def from_dict(cls, d):
        return cls(**d) if d else cls()

    def __str__(self):
        return (f"size={self.size} offset={tuple(self.offset)} "
                f"rotate={self.rotate * 90}deg mirror={'on' if self.mirror else 'off'}")


def dot_frame(point, radius=C.CALIB_DOT_RADIUS):
    """A black projector frame with one white calibration dot."""
    frame = np.zeros((C.PROJECTOR_HEIGHT, C.PROJECTOR_WIDTH, 3), np.uint8)
    cv2.circle(frame, (int(point[0]), int(point[1])), radius, (255, 255, 255), -1, cv2.LINE_AA)
    return frame
