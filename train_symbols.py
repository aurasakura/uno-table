"""
Train the card symbol classifier on crops saved with `python main.py --collect LABEL`.

    python train_symbols.py            # dataset/raw/<label>/*.jpg  ->  models/symbols.pt

Per label, the newest 15% of crops go to validation (a later session, not random
near-duplicate frames). Train crops also get a 180-degree copy, since cards lie either way up.
Horizontal flips are off: a mirrored 7 is not a 7.
"""
import argparse
import os
import shutil

import cv2

RAW, SPLIT = "dataset/raw", "dataset/split"


def build_split(val_frac):
    """Returns the labels that were used."""
    shutil.rmtree(SPLIT, ignore_errors=True)
    used, skipped = [], []
    for label in sorted(os.listdir(RAW)):
        if not os.path.isdir(os.path.join(RAW, label)):
            continue
        files = sorted(os.listdir(os.path.join(RAW, label)))     # names are timestamps
        if len(files) < 2:          # needs at least 1 train + 1 val crop
            skipped.append(f"{label} ({len(files)} crop{'s' if len(files) != 1 else ''})")
            continue
        used.append(label)
        n_val = min(len(files) - 1, max(1, round(len(files) * val_frac)))
        for i, f in enumerate(files):
            part = "val" if i >= len(files) - n_val else "train"
            out = os.path.join(SPLIT, part, label)
            os.makedirs(out, exist_ok=True)
            img = cv2.imread(os.path.join(RAW, label, f))
            cv2.imwrite(os.path.join(out, f), img)
            if part == "train":
                cv2.imwrite(os.path.join(out, "r180_" + f), cv2.rotate(img, cv2.ROTATE_180))
        print(f"{label:8s} {len(files) - n_val:4d} train  {n_val:3d} val")
    print(f"{len(used)} labels used: {' '.join(used)}")
    if skipped:
        print(f"WARNING skipped, fewer than 2 crops: {', '.join(skipped)}. Collect more with --collect.")
    return used


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--freeze", type=int, default=0, help="freeze first N layers (try 5 if few crops)")
    ap.add_argument("--val", type=float, default=0.15)
    a = ap.parse_args()

    os.chdir(os.path.dirname(os.path.abspath(__file__)))     # dataset/ and models/ sit next to this file
    if not os.path.isdir(RAW) or len(build_split(a.val)) < 2:
        raise SystemExit(f"Need at least 2 labels with 2+ crops each in {RAW}. Collect with "
                         f"`python main.py --collect LABEL`.")
    from ultralytics import YOLO
    model = YOLO("yolov8n-cls.pt")
    model.train(data=os.path.abspath(SPLIT), epochs=a.epochs, imgsz=224, freeze=a.freeze,
                fliplr=0.0, project=os.path.abspath("runs"), name="symbols", exist_ok=True)
    os.makedirs("models", exist_ok=True)
    shutil.copy(os.path.join(model.trainer.save_dir, "weights", "best.pt"), "models/symbols.pt")
    print("Saved models/symbols.pt. main.py uses it automatically.")


if __name__ == "__main__":
    main()
