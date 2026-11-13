"""Train and test the provisional four-class YOLOv8 baseline."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path

os.environ.setdefault(
    "YOLO_CONFIG_DIR", str(Path.cwd().resolve() / "artifacts" / "ultralytics-config")
)

import torch
import ultralytics
from ultralytics import YOLO


def git_commit(repo: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--name", default="baseline-v1")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--device", default="0")
    parser.add_argument("--seed", type=int, default=20261113)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo = Path.cwd().resolve()
    data = args.data.resolve()
    model_path = args.model.resolve()
    project = args.project.resolve()
    run_dir = project / args.name
    if run_dir.exists():
        raise SystemExit(f"run directory already exists: {run_dir}")

    model = YOLO(str(model_path))
    train_results = model.train(
        data=str(data),
        epochs=args.epochs,
        patience=args.patience,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        project=str(project),
        name=args.name,
        exist_ok=False,
        pretrained=True,
        seed=args.seed,
        deterministic=True,
        plots=True,
        verbose=True,
    )

    best_path = run_dir / "weights" / "best.pt"
    if not best_path.is_file():
        raise RuntimeError(f"best weight was not produced: {best_path}")
    best_model = YOLO(str(best_path))
    test_metrics = best_model.val(
        data=str(data),
        split="test",
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        project=str(project),
        name=f"{args.name}-test",
        exist_ok=False,
        plots=True,
        verbose=True,
    )

    manifest = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_commit": git_commit(repo),
        "python": platform.python_version(),
        "ultralytics": ultralytics.__version__,
        "torch": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "data": str(data),
        "pretrained_model": str(model_path),
        "best_weight": str(best_path),
        "config": {
            "epochs_requested": args.epochs,
            "patience": args.patience,
            "imgsz": args.imgsz,
            "batch": args.batch,
            "workers": args.workers,
            "device": args.device,
            "seed": args.seed,
        },
        "test_results": {
            key: float(value) for key, value in test_metrics.results_dict.items()
        },
        "test_per_class_map50_95": {
            name: float(value)
            for name, value in zip(test_metrics.names.values(), test_metrics.box.maps)
        },
        "test_speed_ms": {
            key: float(value) for key, value in test_metrics.speed.items()
        },
        "train_result_type": type(train_results).__name__,
    }
    (run_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
