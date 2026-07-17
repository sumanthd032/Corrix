"""Resumes the interrupted Construction-PPE fine-tune from its last
checkpoint, continuing to the original 30-epoch target. Run repeatedly
if interrupted again. Each call picks up from whatever `last.pt`
currently holds.
"""

from pathlib import Path

from ultralytics import YOLO

REPO_ROOT = Path(__file__).resolve().parents[2]
LAST_CKPT = REPO_ROOT / "backend" / "runs" / "ppe_detector" / "weights" / "last.pt"


def main() -> None:
    model = YOLO(str(LAST_CKPT))
    model.train(resume=True)


if __name__ == "__main__":
    main()
