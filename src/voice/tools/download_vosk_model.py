"""下载并解压 Vosk 离线中文模型到 src/voice/models/vosk-cn。

用法：
  python -m voice.tools.download_vosk_model
  python -m voice.tools.download_vosk_model --url <自定义模型url> --out <目标目录>

说明：
- 默认下载 vosk-model-small-cn-0.15（小模型，约 40MB，识别“帮我分类”足够）。
- 模型来自 https://alphacephei.com/vosk/models ，国内通常可直连；若被墙请手动下载后解压。
- 解压后请确认目录内有 conf/ 与 *.am/.conf 等模型文件（即模型根目录）。
"""

from __future__ import annotations

import argparse
import os
import sys
import zipfile

DEFAULT_URL = "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.15.zip"
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "vosk-cn")


def _download(url: str, dest_zip: str) -> None:
    try:
        import urllib.request
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("当前环境无法导入 urllib.request") from e
    print(f"[download] {url}\n  -> {dest_zip}")
    urllib.request.urlretrieve(url, dest_zip)  # noqa: S310  # 用户显式触发的下载


def _unzip(zip_path: str, out_dir: str) -> str:
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        # 模型通常打包在单层根目录内（如 vosk-model-small-cn-0.15/...）
        top = names[0].split("/", 1)[0] if names and names[0].endswith("/") else ""
        z.extractall(out_dir)
    # 若解压出的是带版本号的根目录，则把内容搬平到 out_dir 根，方便默认路径直接加载
    if top:
        nested = os.path.join(out_dir, top)
        if os.path.isdir(nested):
            for item in os.listdir(nested):
                os.replace(os.path.join(nested, item), os.path.join(out_dir, item))
            os.rmdir(nested)
    return out_dir


def main() -> int:
    ap = argparse.ArgumentParser(description="下载 Vosk 中文模型")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    zip_path = os.path.join(args.out, "vosk-cn.zip")
    try:
        _download(args.url, zip_path)
        _unzip(zip_path, args.out)
    except Exception as e:  # noqa: BLE001
        print(f"[error] 下载/解压失败：{e}", file=sys.stderr)
        print("可手动从 https://alphacephei.com/vosk/models 下载后解压到：", args.out, file=sys.stderr)
        return 1
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
    print(f"[done] Vosk 模型就绪：{args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
