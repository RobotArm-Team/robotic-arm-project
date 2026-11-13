"""Create review-only LabelMe solid-color-face boxes for course blocks.

Usage:
    python tools/prelabel_course_blocks.py SOURCE_IMAGES OUTPUT_IMAGES

The output directory must not exist. Each image is copied beside its draft JSON.
Only the large blue/red/green/yellow face is drafted. Every draft must be
checked in Model Adapter before it counts as a label.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

import cv2
import numpy as np


COLORS = (
    # Blue-tinted white side panels otherwise merge with the blue top face.
    ("recyclable", ((90, 100, 35), (135, 255, 255))),
    ("hazardous", ((0, 75, 35), (13, 255, 255))),
    ("kitchen", ((36, 45, 30), (88, 255, 255))),
    ("other", ((17, 65, 65), (42, 255, 255))),
)
MIN_FACE_AREA = 2600
MIN_BROAD_ROWS = 60


def longest_true_run(values: np.ndarray) -> tuple[int, int] | None:
    """Return the inclusive bounds of the longest consecutive True run."""
    best = None
    start = None
    for index, value in enumerate(values):
        if value and start is None:
            start = index
        if start is not None and (not value or index == len(values) - 1):
            end = index if value and index == len(values) - 1 else index - 1
            if best is None or end - start > best[1] - best[0]:
                best = (start, end)
            start = None
    return best


def read_image(path: Path) -> np.ndarray:
    """OpenCV's Windows file reader may reject Chinese path components."""
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot decode image: {path}")
    return image


def color_masks(hsv: np.ndarray):
    for label, (lower, upper) in COLORS:
        mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
        if label == "hazardous":
            mask |= cv2.inRange(
                hsv, np.array((170, 75, 35)), np.array((179, 255, 255))
            )
        yield label, mask


def draft_boxes(image: np.ndarray) -> list[dict]:
    height, width = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    kernel_open = np.ones((5, 5), dtype=np.uint8)
    kernel_close = np.ones((7, 7), dtype=np.uint8)
    shapes = []
    for label, mask in color_masks(hsv):
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_open)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close)
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
        for component in range(1, count):
            x, y, face_width, face_height, area = map(int, stats[component])
            if area < MIN_FACE_AREA or face_width < 45 or face_height < 35:
                continue
            component_mask = mask[y : y + face_height, x : x + face_width]
            row_pixels = np.count_nonzero(component_mask, axis=1)
            # A real top face contains a long consecutive run of broad,
            # solid-color rows. Printed pictures and slightly tinted white
            # side faces do not, so they are discarded here.
            broad_run = longest_true_run(row_pixels >= face_width * 0.35)
            if broad_run is None or broad_run[1] - broad_run[0] + 1 < MIN_BROAD_ROWS:
                continue

            # Course labels target only the large solid-color face, not the
            # whole cube. A face seen as a diamond narrows near both tips, so
            # keep its full color-component height. A near-front-on face has
            # its broad run at the top; stop shortly after that run so colored
            # outlines down the illustrated sides cannot lengthen the box.
            if broad_run[0] >= 20:
                face_bottom = face_height
            else:
                face_bottom = min(
                    face_height,
                    broad_run[1] + 1 + round(face_width * 0.08),
                )
            face_pixels = np.argwhere(component_mask[:face_bottom] > 0)
            face_left = int(face_pixels[:, 1].min())
            face_right = int(face_pixels[:, 1].max()) + 1
            padding = 5
            left = max(0, x + face_left - padding)
            top = max(0, y - padding)
            right = min(width - 1, x + face_right + padding)
            bottom = min(height - 1, y + face_bottom + padding)
            shapes.append(
                {
                    "label": label,
                    "points": [[left, top], [right, bottom]],
                    "group_id": None,
                    "shape_type": "rectangle",
                    "flags": {},
                }
            )
    return sorted(shapes, key=lambda shape: (shape["points"][0][1], shape["points"][0][0]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    if not source.is_dir():
        parser.error(f"Source directory does not exist: {source}")
    if output.exists():
        parser.error(f"Output already exists; refusing to overwrite: {output}")
    images = sorted(source.glob("*.jpg"), key=lambda path: int(path.stem))
    if not images:
        parser.error(f"No JPG images found in: {source}")

    output.mkdir(parents=True)
    rows = []
    for path in images:
        image = read_image(path)
        shapes = draft_boxes(image)
        height, width = image.shape[:2]
        target_image = output / path.name
        shutil.copy2(path, target_image)
        target_json = output / f"{path.stem}.json"
        target_json.write_text(
            json.dumps(
                {
                    "version": "5.0.1",
                    "flags": {},
                    "shapes": shapes,
                    "imagePath": path.name,
                    "imageData": None,
                    "imageHeight": height,
                    "imageWidth": width,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        rows.append(
            {
                "image": path.name,
                "draft_boxes": len(shapes),
                "draft_classes": ";".join(shape["label"] for shape in shapes),
                "review_status": "pending",
            }
        )

    with (output.parent / "review.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Drafted {len(rows)} images in {output}")
    print(f"Images with no draft boxes: {sum(not row['draft_boxes'] for row in rows)}")
    print(f"Draft boxes: {sum(row['draft_boxes'] for row in rows)}")
    print(f"Review list: {output.parent / 'review.csv'}")


if __name__ == "__main__":
    main()
