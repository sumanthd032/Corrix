"""Fine-tunes YOLO11n on the real, open Ultralytics Construction-PPE
dataset, per CORRIX_BUILD_PLAN.md Step 6. Zero-shot COCO-pretrained YOLO
only knows "person"; it has no concept of a hardhat or a missing one,
so fine-tuning on this dataset is what actually makes the Site Safety
Observer's CV signal real PPE detection, not just person-counting.

Run from backend/: python scripts/train_ppe_model.py --epochs N
"""

import argparse
from pathlib import Path

from ultralytics import YOLO

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO_ROOT / "backend" / "runs"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--batch", type=int, default=8)
    args = parser.parse_args()

    model = YOLO("yolo11n.pt")
    model.train(
        data="construction-ppe.yaml",
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        project=str(RUNS_DIR),
        name="ppe_detector",
        exist_ok=True,
        device="cpu",
    )


if __name__ == "__main__":
    main()
