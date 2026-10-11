"""
YOLOv8 symbol recognition for recognise_symbol().
Model: pretrained UNO weights from github.com/Stormynova/Uno_Card_detection (MIT).
Its labels look like 'lred-7', 'lblueskip-20', 'lcolor-40' (wild), 'lcolor-400' (wild +4).
"""
import re

import config as C

_model = None
_failed = False


def _load():
    global _model, _failed
    if _model is None and not _failed:
        try:
            from ultralytics import YOLO
            _model = YOLO(C.YOLO_MODEL)
        except Exception as e:   # missing package or model file: fall back to colour only
            print(f"[yolo] disabled: {e}")
            _failed = True
    return _model


def label_to_card(name):
    """'lred-7' -> ('red', '7'), 'lgreenskip-20' -> ('green', 'skip'), 'lcolor-400' -> ('wild', 'wild4')."""
    m = re.fullmatch(r"l(blue|green|red|yellow|color2|color)(flip|revers|skip)?-(\d+)", name)
    if not m:
        return None, None
    colour, action, num = m.groups()
    if colour == "color":
        return "wild", {"400": "wild4", "40": "wild"}.get(num)
    if colour == "color2":
        return "wild", "wild4"
    if action or num == "20":   # +2 is the only action left once skip/reverse are named
        return colour, {"revers": "reverse", "skip": "skip"}.get(action, "draw2")
    return colour, ("0" if num == "10" else num)


def recognise(image_bgr, zone=None):
    """Best (colour, symbol, confidence) whose box centre lies inside zone (x0, y0, x1, y1),
    or anywhere if zone is None. (None, None, 0.0) if nothing is found."""
    global _model, _failed
    if not C.YOLO_ENABLED or _load() is None:
        return None, None, 0.0
    try:
        res = _model(image_bgr, conf=C.YOLO_CONF, verbose=False)[0]
    except Exception as e:      # never crash the game loop: fall back to colour only
        print(f"[yolo] inference failed, disabled: {e}")
        _model, _failed = None, True
        return None, None, 0.0
    best = None
    for (bx0, by0, bx1, by1), cls, conf in zip(res.boxes.xyxy.tolist(), res.boxes.cls.tolist(), res.boxes.conf.tolist()):
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        if zone and not (zone[0] <= cx <= zone[2] and zone[1] <= cy <= zone[3]):
            continue
        if best is None or conf > best[2]:
            best = (*label_to_card(_model.names[int(cls)]), conf)
    return best or (None, None, 0.0)


# ---------------------------------------------------------------------
# Our own symbol classifier (trained by train_symbols.py on the real deck)
# ---------------------------------------------------------------------
_cls = None
_cls_failed = False


def _disable_classifier(why):
    global _cls, _cls_failed
    print(f"[symbols] classifier disabled, using the pretrained detector: {why}")
    _cls, _cls_failed = None, True


def has_classifier():
    global _cls
    import os
    if _cls is None and not _cls_failed and C.YOLO_ENABLED and os.path.exists(C.SYMBOL_MODEL):
        try:
            from ultralytics import YOLO
            _cls = YOLO(C.SYMBOL_MODEL)
        except Exception as e:
            _disable_classifier(e)
    return _cls is not None


def classify(card_bgr):
    """Symbol ('7', 'skip', ...) for a straightened card crop, or None if unsure.
    Tries the crop and its 180-degree turn, since cards can lie either way up."""
    import cv2
    best_name, best_p = None, 0.0
    accepted_names = set()
    try:
        for img in (card_bgr, cv2.rotate(card_bgr, cv2.ROTATE_180)):
            p = _cls(img, verbose=False)[0].probs
            if float(p.top1conf) >= C.SYMBOL_CONF:
                accepted_names.add(_cls.names[p.top1])
            if p.top1conf > best_p:
                best_name, best_p = _cls.names[p.top1], float(p.top1conf)
    except Exception as e:
        _disable_classifier(e)
        return None
    # Confident 6/9 (or other) disagreement between orientations must abstain.
    if len(accepted_names) > 1:
        return None
    return best_name if best_p >= C.SYMBOL_CONF else None
