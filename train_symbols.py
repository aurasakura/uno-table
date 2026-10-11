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
    shutil.rmtree(SPLIT, ignore_errors=True)
    for label in sorted(os.listdir(RAW)):
        files = sorted(os.listdir(os.path.join(RAW, label)))     # names are timestamps
        n_val = max(1, round(len(files) * val_frac))
        for i, f in enumerate(files):
            part = "val" if i >= len(files) - n_val else "train"
            out = os.path.join(SPLIT, part, label)
            os.makedirs(out, exist_ok=True)
            img = cv2.imread(os.path.join(RAW, label, f))
            cv2.imwrite(os.path.join(out, f), img)
            if part == "train":
                cv2.imwrite(os.path.join(out, "r180_" + f), cv2.rotate(img, cv2.ROTATE_180))
        print(f"{label:8s} {len(files) - n_val:4d} train  {n_val:3d} val")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--freeze", type=int, default=0, help="freeze first N layers (try 5 if few crops)")
    ap.add_argument("--val", type=float, default=0.15)
    a = ap.parse_args()

    build_split(a.val)
    from ultralytics import YOLO
    model = YOLO("yolov8n-cls.pt")
    model.train(data=os.path.abspath(SPLIT), epochs=a.epochs, imgsz=224, freeze=a.freeze,
                fliplr=0.0, project=os.path.abspath("runs"), name="symbols", exist_ok=True)
    os.makedirs("models", exist_ok=True)
    shutil.copy(os.path.join(model.trainer.save_dir, "weights", "best.pt"), "models/symbols.pt")
    print("Saved models/symbols.pt. main.py uses it automatically.")


if __name__ == "__main__":
    main()
