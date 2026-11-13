"""Build a group-aware YOLO dataset from reviewed LabelMe annotations.

Near-duplicate images are kept in one split to reduce train/test leakage.
The generated dataset is local runtime data and should not be committed.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


CLASS_NAMES = ("recyclable", "hazardous", "kitchen", "other")
CLASS_IDS = {name: index for index, name in enumerate(CLASS_NAMES)}
SPLITS = ("train", "val", "test")
SPLIT_RATIOS = (0.7, 0.2, 0.1)


@dataclass(frozen=True)
class Record:
    stem: str
    image_path: Path
    json_path: Path
    labels: tuple[str, ...]
    width: int
    height: int
    shapes: tuple[dict, ...]
    thumbnail: np.ndarray
    phash: np.ndarray


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def read_image(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"cannot decode image: {path}")
    return image


def image_features(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    thumbnail = cv2.resize(gray, (64, 48)).astype(np.float32) / 255.0
    dct = cv2.dct(cv2.resize(gray, (32, 32)).astype(np.float32))[:8, :8]
    phash = dct > dct[1:, 1:].mean()
    return thumbnail, phash


def load_records(source: Path) -> list[Record]:
    records = []
    for image_path in sorted(source.glob("*.jpg"), key=lambda path: int(path.stem)):
        json_path = image_path.with_suffix(".json")
        if not json_path.is_file():
            raise ValueError(f"missing LabelMe JSON: {json_path}")
        data = json.loads(json_path.read_text(encoding="utf-8"))
        image = read_image(image_path)
        height, width = image.shape[:2]
        if (data.get("imageWidth"), data.get("imageHeight")) != (width, height):
            raise ValueError(f"image size mismatch: {json_path}")
        shapes = tuple(data.get("shapes", ()))
        if not shapes:
            raise ValueError(f"reviewed image has no boxes: {json_path}")
        labels = tuple(shape["label"] for shape in shapes)
        unknown = sorted(set(labels) - set(CLASS_NAMES))
        if unknown:
            raise ValueError(f"unknown labels in {json_path}: {unknown}")
        thumbnail, phash = image_features(image)
        records.append(
            Record(
                stem=image_path.stem,
                image_path=image_path,
                json_path=json_path,
                labels=labels,
                width=width,
                height=height,
                shapes=shapes,
                thumbnail=thumbnail,
                phash=phash,
            )
        )
    if not records:
        raise ValueError(f"no JPG files found in {source}")
    return records


def similarity_groups(
    records: list[Record], *, phash_distance: int, thumbnail_mae: float
) -> list[list[int]]:
    union_find = UnionFind(len(records))
    for left in range(len(records)):
        for right in range(left + 1, len(records)):
            hamming = int(np.count_nonzero(records[left].phash != records[right].phash))
            if hamming > phash_distance:
                continue
            mae = float(
                np.mean(np.abs(records[left].thumbnail - records[right].thumbnail))
            )
            if mae <= thumbnail_mae:
                union_find.union(left, right)
    groups: dict[int, list[int]] = {}
    for index in range(len(records)):
        groups.setdefault(union_find.find(index), []).append(index)
    return sorted(groups.values(), key=lambda group: (-len(group), group[0]))


def group_counts(group: list[int], records: list[Record]) -> Counter:
    counts = Counter()
    for index in group:
        counts.update(records[index].labels)
    return counts


def choose_splits(
    groups: list[list[int]], records: list[Record], *, seed: int, trials: int
) -> list[int]:
    rng = np.random.default_rng(seed)
    group_sizes = np.array([len(group) for group in groups], dtype=np.float64)
    group_classes = np.zeros((len(groups), len(CLASS_NAMES)), dtype=np.float64)
    for group_index, group in enumerate(groups):
        counts = group_counts(group, records)
        for class_index, name in enumerate(CLASS_NAMES):
            group_classes[group_index, class_index] = counts[name]
    image_targets = len(records) * np.array(SPLIT_RATIOS, dtype=np.float64)
    total_classes = group_classes.sum(axis=0)
    class_targets = np.outer(np.array(SPLIT_RATIOS), total_classes)

    best_assignment = None
    best_score = float("inf")
    batch_size = 1000
    for start in range(0, trials, batch_size):
        current_size = min(batch_size, trials - start)
        assignments = rng.choice(
            3, size=(current_size, len(groups)), p=SPLIT_RATIOS
        )
        image_counts = np.stack(
            [(assignments == split_index) @ group_sizes for split_index in range(3)],
            axis=1,
        )
        class_counts = np.stack(
            [
                (assignments == split_index).astype(np.float64) @ group_classes
                for split_index in range(3)
            ],
            axis=1,
        )
        scores = 5.0 * np.sum(
            ((image_counts - image_targets) / image_targets) ** 2, axis=1
        )
        scores += np.sum(
            ((class_counts - class_targets) / class_targets) ** 2,
            axis=(1, 2),
        )
        scores += 100.0 * np.sum(class_counts == 0, axis=(1, 2))
        best_in_batch = int(np.argmin(scores))
        if float(scores[best_in_batch]) < best_score:
            best_score = float(scores[best_in_batch])
            best_assignment = assignments[best_in_batch].tolist()
    if best_assignment is None:
        raise RuntimeError("could not create dataset split")
    return best_assignment


def yolo_lines(record: Record) -> list[str]:
    lines = []
    for shape in record.shapes:
        if shape.get("shape_type") != "rectangle" or len(shape.get("points", ())) != 2:
            raise ValueError(f"non-rectangle shape in {record.json_path}")
        (x1, y1), (x2, y2) = shape["points"]
        left, right = sorted((float(x1), float(x2)))
        top, bottom = sorted((float(y1), float(y2)))
        if not (0 <= left < right <= record.width and 0 <= top < bottom <= record.height):
            raise ValueError(f"out-of-bounds box in {record.json_path}: {shape['points']}")
        center_x = (left + right) / 2 / record.width
        center_y = (top + bottom) / 2 / record.height
        box_width = (right - left) / record.width
        box_height = (bottom - top) / record.height
        lines.append(
            f"{CLASS_IDS[shape['label']]} {center_x:.8f} {center_y:.8f} "
            f"{box_width:.8f} {box_height:.8f}"
        )
    return lines


def build_dataset(
    records: list[Record],
    groups: list[list[int]],
    assignments: list[int],
    output: Path,
    *,
    seed: int,
    phash_distance: int,
    thumbnail_mae: float,
) -> None:
    if output.exists():
        raise ValueError(f"output already exists; refusing to overwrite: {output}")
    for split in SPLITS:
        (output / "images" / split).mkdir(parents=True)
        (output / "labels" / split).mkdir(parents=True)

    rows = []
    summary = {split: {"images": 0, "boxes": Counter()} for split in SPLITS}
    for group_id, (group, split_index) in enumerate(zip(groups, assignments), start=1):
        split = SPLITS[split_index]
        for record_index in group:
            record = records[record_index]
            shutil.copy2(record.image_path, output / "images" / split / record.image_path.name)
            label_path = output / "labels" / split / f"{record.stem}.txt"
            label_path.write_text("\n".join(yolo_lines(record)) + "\n", encoding="utf-8")
            summary[split]["images"] += 1
            summary[split]["boxes"].update(record.labels)
            rows.append(
                {
                    "image": record.image_path.name,
                    "split": split,
                    "similarity_group": group_id,
                    "classes": ";".join(record.labels),
                    "box_count": len(record.labels),
                }
            )

    data_yaml = (
        f"path: {output.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        "names:\n"
        + "".join(f"  {index}: {name}\n" for index, name in enumerate(CLASS_NAMES))
    )
    (output / "data.yaml").write_text(data_yaml, encoding="utf-8")
    with (output / "split_manifest.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: int(Path(row["image"]).stem)))

    serializable_summary = {
        "seed": seed,
        "phash_distance": phash_distance,
        "thumbnail_mae": thumbnail_mae,
        "similarity_groups": len(groups),
        "largest_group": max(map(len, groups)),
        "splits": {
            split: {
                "images": values["images"],
                "boxes": {name: values["boxes"][name] for name in CLASS_NAMES},
            }
            for split, values in summary.items()
        },
    }
    (output / "summary.json").write_text(
        json.dumps(serializable_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(serializable_summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=20261113)
    parser.add_argument("--trials", type=int, default=30000)
    parser.add_argument("--phash-distance", type=int, default=12)
    parser.add_argument("--thumbnail-mae", type=float, default=0.05)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if not source.is_dir():
        raise SystemExit(f"source does not exist: {source}")
    records = load_records(source)
    groups = similarity_groups(
        records,
        phash_distance=args.phash_distance,
        thumbnail_mae=args.thumbnail_mae,
    )
    assignments = choose_splits(groups, records, seed=args.seed, trials=args.trials)
    build_dataset(
        records,
        groups,
        assignments,
        output,
        seed=args.seed,
        phash_distance=args.phash_distance,
        thumbnail_mae=args.thumbnail_mae,
    )


if __name__ == "__main__":
    main()
