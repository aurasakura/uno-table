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
        return "wild", ("wild4" if num == "400" else None)
    if colour == "color2":
        return "wild", "wild4"
    if action or num == "20":   # +2 is the only action left once skip/reverse are named
        return colour, {"revers": "reverse", "skip": "skip"}.get(action, "draw2")
    return colour, ("0" if num == "10" else num)


def recognise(image_bgr, zone=None):
    """Best (colour, symbol, confidence) whose box centre lies inside zone (x0, y0, x1, y1),
    or anywhere if zone is None. (None, None, 0.0) if nothing is found."""
    if not C.YOLO_ENABLED or _load() is None:
        return None, None, 0.0
    res = _model(image_bgr, conf=C.YOLO_CONF, verbose=False)[0]
    best = None
    for (bx0, by0, bx1, by1), cls, conf in zip(res.boxes.xyxy.tolist(), res.boxes.cls.tolist(), res.boxes.conf.tolist()):
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        if zone and not (zone[0] <= cx <= zone[2] and zone[1] <= cy <= zone[3]):
            continue
        if best is None or conf > best[2]:
            best = (*label_to_card(_model.names[int(cls)]), conf)
    return best or (None, None, 0.0)
