"""Download real local OpenVINO vision models for the MVP demo.

Usage:
    python -m backend.scripts.setup_openvino_models

The backend auto-discovers these files under ``backend/models/openvino``. No
cloud API is used at runtime; this script only fetches model files once.
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from backend.runtimes.openvino_vision_runtime import DEFAULT_MODELS_DIR


@dataclass(frozen=True)
class ModelFile:
    name: str
    url: str
    target: Path


def _default_files(models_dir: Path) -> list[ModelFile]:
    object_dir = models_dir / "ssdlite_mobilenet_v2_fp16"
    ocr_det_dir = models_dir / "horizontal-text-detection-0001" / "FP32"
    ocr_rec_dir = models_dir / "text-recognition-0012" / "FP32"
    return [
        ModelFile(
            "object detector XML",
            "https://huggingface.co/katuni4ka/ssdlite_mobilenet_v2_fp16/resolve/main/ssdlite_mobilenet_v2_fp16.xml",
            object_dir / "ssdlite_mobilenet_v2_fp16.xml",
        ),
        ModelFile(
            "object detector BIN",
            "https://huggingface.co/katuni4ka/ssdlite_mobilenet_v2_fp16/resolve/main/ssdlite_mobilenet_v2_fp16.bin",
            object_dir / "ssdlite_mobilenet_v2_fp16.bin",
        ),
        ModelFile(
            "OCR text detector XML",
            "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2022.1/models_bin/2/horizontal-text-detection-0001/FP32/horizontal-text-detection-0001.xml",
            ocr_det_dir / "horizontal-text-detection-0001.xml",
        ),
        ModelFile(
            "OCR text detector BIN",
            "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2022.1/models_bin/2/horizontal-text-detection-0001/FP32/horizontal-text-detection-0001.bin",
            ocr_det_dir / "horizontal-text-detection-0001.bin",
        ),
        ModelFile(
            "OCR recognizer XML",
            "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2022.1/models_bin/2/text-recognition-0012/FP32/text-recognition-0012.xml",
            ocr_rec_dir / "text-recognition-0012.xml",
        ),
        ModelFile(
            "OCR recognizer BIN",
            "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2022.1/models_bin/2/text-recognition-0012/FP32/text-recognition-0012.bin",
            ocr_rec_dir / "text-recognition-0012.bin",
        ),
    ]


def _download(file: ModelFile, *, force: bool = False) -> None:
    file.target.parent.mkdir(parents=True, exist_ok=True)
    if file.target.exists() and file.target.stat().st_size > 0 and not force:
        print(f"skip: {file.name} already exists at {file.target}")
        return

    tmp_path = file.target.with_suffix(file.target.suffix + ".download")
    if tmp_path.exists():
        tmp_path.unlink()
    print(f"download: {file.name}")
    print(f"  from {file.url}")
    print(f"  to   {file.target}")
    try:
        with urllib.request.urlopen(file.url, timeout=120) as response:
            with tmp_path.open("wb") as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
    except (urllib.error.URLError, TimeoutError) as exc:
        if tmp_path.exists():
            tmp_path.unlink()
        raise RuntimeError(f"failed to download {file.name}: {exc}") from exc
    tmp_path.replace(file.target)


def _validate_pair(xml_path: Path) -> None:
    if not xml_path.exists() or xml_path.stat().st_size <= 0:
        raise RuntimeError(f"missing model XML: {xml_path}")
    bin_path = xml_path.with_suffix(".bin")
    if not bin_path.exists() or bin_path.stat().st_size <= 0:
        raise RuntimeError(f"missing model BIN: {bin_path}")


def _validate(models_dir: Path) -> None:
    _validate_pair(models_dir / "ssdlite_mobilenet_v2_fp16" / "ssdlite_mobilenet_v2_fp16.xml")
    _validate_pair(
        models_dir
        / "horizontal-text-detection-0001"
        / "FP32"
        / "horizontal-text-detection-0001.xml"
    )
    _validate_pair(models_dir / "text-recognition-0012" / "FP32" / "text-recognition-0012.xml")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download local OpenVINO vision models")
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=DEFAULT_MODELS_DIR,
        help="target directory; defaults to backend/models/openvino",
    )
    parser.add_argument("--force", action="store_true", help="re-download existing files")
    args = parser.parse_args()

    models_dir = args.models_dir.resolve()
    print(f"models dir: {models_dir}")
    try:
        for file in _default_files(models_dir):
            _download(file, force=args.force)
        _validate(models_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("")
    print("OpenVINO vision models are ready.")
    print("The backend will auto-discover them. Explicit env overrides still work:")
    print(f'  VISION_MODELS_DIR="{models_dir}"')
    print(
        f'  VISION_DET_MODEL="{models_dir / "ssdlite_mobilenet_v2_fp16" / "ssdlite_mobilenet_v2_fp16.xml"}"'
    )
    print(
        f'  VISION_OCR_DET_MODEL="{models_dir / "horizontal-text-detection-0001" / "FP32" / "horizontal-text-detection-0001.xml"}"'
    )
    print(
        f'  VISION_OCR_REC_MODEL="{models_dir / "text-recognition-0012" / "FP32" / "text-recognition-0012.xml"}"'
    )


if __name__ == "__main__":
    main()
