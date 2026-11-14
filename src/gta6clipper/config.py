"""Paths and defaults."""
from __future__ import annotations

import os

APP_NAME = "gta6-clipper"
CACHE_DIR = os.environ.get("GTA6_CLIPPER_CACHE") or os.path.expanduser(f"~/.cache/{APP_NAME}")

MODEL_DIR = os.path.join(CACHE_DIR, "models")
WHISPER_MODEL = os.path.join(MODEL_DIR, "ggml-large-v3-turbo.bin")
FACECAM_MODEL = os.path.join(MODEL_DIR, "face_detection_yunet_2023mar.onnx")

FACECAM_MODEL_URL = (
    "https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/face_detection_yunet/"
    "face_detection_yunet_2023mar.onnx"
)

DEFAULT_OUT_DIR = os.path.join(os.getcwd(), "clips")
DEFAULT_CLIP_COUNT = 3
DEFAULT_CLIP_MIN_SECONDS = 20
DEFAULT_CLIP_MAX_SECONDS = 60
WINDOW_MINUTES = 12
MIN_SCORE = 70


def ensure_dirs() -> None:
    os.makedirs(MODEL_DIR, exist_ok=True)


def slugify(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in (text or "stream")]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:60] or "stream"


def work_dir(out_dir: str, title: str) -> str:
    path = os.path.join(out_dir, slugify(title))
    os.makedirs(path, exist_ok=True)
    return path
