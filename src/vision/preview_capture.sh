#!/usr/bin/env bash
# Open a live camera preview for one labeled capture session on the 200DK.
# Usage: bash vision/preview_capture.sh recyclable test-blue-01

set -euo pipefail

label="${1:-}"
session="${2:-preview-$(date +%Y%m%d-%H%M%S)}"
output_root="${OUTPUT_ROOT:-/home/HwHiAiUser/RobotArm/data/raw/captures}"
python_bin="${PYTHON_BIN:-/root/miniconda3/envs/ros-arm-env/bin/python}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "$label" in
  recyclable|hazardous|kitchen|other) ;;
  *)
    echo "Usage: bash vision/preview_capture.sh {recyclable|hazardous|kitchen|other} [session]" >&2
    exit 2
    ;;
esac

exec "$python_bin" "$script_dir/capture_blocks.py" \
  --label "$label" \
  --session "$session" \
  --output "$output_root"
