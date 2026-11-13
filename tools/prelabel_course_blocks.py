"""Create review-only LabelMe draft boxes for the four course block colors.

Usage:
    python tools/prelabel_course_blocks.py SOURCE_IMAGES OUTPUT_IMAGES

The output directory must not exist. Each image is copied beside its draft JSON.
Every draft must be checked in Model Adapter before it counts as a label.
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
    ("recyclable", ((90, 55, 35), (135, 255, 255))),
    ("hazardous", ((0, 75, 35), (13, 255, 255))),
    ("kitchen", ((36, 45, 30), (88, 255, 255))),
    ("other", ((17, 65, 65), (42, 255, 255))),
)
MIN_FACE_AREA = 2600


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
    kernel_face = np.ones((11, 11), dtype=np.uint8)
    shapes = []
    for label, mask in color_masks(hsv):
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_open)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close)
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
        for component in range(1, count):
            x, y, face_width, face_height, area = map(int, stats[component])
            if area < MIN_FACE_AREA or face_width < 45 or face_height < 35:
                continue
            # Thin colored outlines can continue down the illustrated sides.
            # Opening with a larger kernel isolates the broad colored face.
            face = cv2.morphologyEx(
                mask[y : y + face_height, x : x + face_width],
                cv2.MORPH_OPEN,
                kernel_face,
            )
            face_count, _, face_stats, _ = cv2.connectedComponentsWithStats(face)
            if face_count > 1:
                core = max(face_stats[1:], key=lambda row: row[cv2.CC_STAT_AREA])
                solid_bottom = y + int(core[cv2.CC_STAT_TOP] + core[cv2.CC_STAT_HEIGHT])
            else:
                solid_bottom = y + face_height
            # The visible color face is normally the top face. Include the
            # illustrated side faces in a deliberately reviewable draft box.
            left = max(0, x - 12)
            top = max(0, y - 8)
            right = min(width - 1, x + face_width + 12)
            bottom = min(height - 1, solid_bottom + round(face_width * 0.42))
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
