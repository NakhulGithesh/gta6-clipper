"""Find the webcam inset in a gameplay VOD.

A stream VOD is a game with the streamer composited into a corner. That inset
has no border and the game behind it moves as much as the face does, so the
reliable signals are: a face, small, off-centre, anchored to an edge.

OpenCV's YuNet detector does the face part (one small ONNX file, no training
data shipped here). The rest is geometry.
"""
from __future__ import annotations

import os

CORNER_MARGIN = 0.20      # how close to an edge still counts as anchored to it
MAX_SUBJECT_HEIGHT = 0.35  # fraction of frame height; a presenter filling the shot is not an inset
MIN_OFFSET = 0.18          # horizontal distance from centre, as a fraction of frame width
MIN_INSET_HEIGHT = 0.10
MAX_INSET_HEIGHT = 0.38
MAX_CENTRE_SPREAD = 0.05   # a pinned webcam does not move; a person in a room does
FACE_WIDTHS = 3.0          # a webcam frames head and shoulders; detectors return the face
INSET_ASPECT = 16 / 9.0


def is_cornered(box: tuple[int, int, int, int], frame_w: int, frame_h: int) -> bool:
    """Does this face look like a webcam inset rather than the shot itself?"""
    x, y, w, h = box
    if h > frame_h * MAX_SUBJECT_HEIGHT:
        return False
    cx = (x + w / 2.0) / frame_w
    if abs(cx - 0.5) < MIN_OFFSET:
        return False
    near_edge = (
        x <= frame_w * CORNER_MARGIN
        or (x + w) >= frame_w * (1 - CORNER_MARGIN)
        or y <= frame_h * CORNER_MARGIN
        or (y + h) >= frame_h * (1 - CORNER_MARGIN)
    )
    return near_edge


def inset_from_face(
    box: tuple[int, int, int, int], frame_w: int, frame_h: int, widths: float = FACE_WIDTHS
) -> tuple[int, int, int, int]:
    """Grow a detected face into the 16:9 rectangle the webcam window sits in."""
    x, y, w, h = box
    new_w = min(frame_w, int(round(w * widths)))
    new_h = min(frame_h, int(round(new_w / INSET_ASPECT)))
    cx, cy = x + w / 2.0, y + h / 2.0
    new_x = int(round(max(0, min(cx - new_w / 2.0, frame_w - new_w))))
    new_y = int(round(max(0, min(cy - new_h * 0.45, frame_h - new_h))))
    return new_x, new_y, new_w, new_h


def stable_box(
    boxes: list[tuple[int, int, int, int]], frame_w: int, frame_h: int, min_agree: int = 3
) -> tuple[int, int, int, int] | None:
    """Median of the inset boxes that agree with each other, or None.

    A subject that moves between samples is a person in a room, not a pinned
    webcam, so boxes that disagree are rejected rather than averaged.
    """
    if len(boxes) < min_agree:
        return None
    import numpy as np

    arr = np.array(boxes, dtype=float)
    centres_x = arr[:, 0] + arr[:, 2] / 2.0
    centres_y = arr[:, 1] + arr[:, 3] / 2.0
    mid_x, mid_y = np.median(centres_x), np.median(centres_y)
    tolerance = frame_w * MAX_CENTRE_SPREAD
    close = (np.abs(centres_x - mid_x) <= tolerance) & (np.abs(centres_y - mid_y) <= tolerance)
    if int(close.sum()) < max(min_agree, 0.6 * len(boxes)):
        return None
    arr = arr[close]
    median = tuple(int(round(v)) for v in np.median(arr, axis=0))
    height = median[3]
    if not (MIN_INSET_HEIGHT * frame_h <= height <= MAX_INSET_HEIGHT * frame_h):
        return None
    return median  # type: ignore[return-value]


def facecam_box(
    video_path: str, model_path: str, samples: int = 10
) -> tuple[int, int, int, int] | None:
    """The webcam inset rectangle in a video, or None when there is no usable one."""
    if not os.path.exists(model_path) or not os.path.exists(video_path):
        return None
    try:
        os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
        import cv2
    except ImportError:
        return None

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if total <= 0 or not frame_w:
        cap.release()
        return None

    try:
        detector = cv2.FaceDetectorYN.create(str(model_path), "", (320, 320), 0.6, 0.3, 5000)
    except Exception:
        cap.release()
        return None

    boxes: list[tuple[int, int, int, int]] = []
    try:
        for i in range(samples):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(i * total / samples))
            ok, frame = cap.read()
            if not ok:
                continue
            detector.setInputSize((frame.shape[1], frame.shape[0]))
            _, faces = detector.detect(frame)
            if faces is None:
                continue
            for face in faces:
                x, y, w, h = (int(round(float(v))) for v in face[:4])
                if not is_cornered((x, y, w, h), frame_w, frame_h):
                    continue
                boxes.append(inset_from_face((x, y, w, h), frame_w, frame_h))
                break
    finally:
        cap.release()

    if len(boxes) < max(3, samples // 3):
        return None
    return stable_box(boxes, frame_w, frame_h)
