"""Captions: word-by-word highlighted captions and the hook, rendered with Pillow.

Homebrew's ffmpeg has no libass and no drawtext, so text cannot be burned in
by ffmpeg itself. Instead the caption track is drawn here, into a transparent
video that ffmpeg overlays onto the clip. One layer for the captions, one for
the hook.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

DEFAULT_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/SFNSDisplay.ttf",
)

CAPTION_HEIGHT = 360
HOOK_HEIGHT = 360
CAPTION_TOP = 1300
HOOK_TOP = 420
SAFE_MARGIN = 70


def font_path(preferred: str | None = None) -> str | None:
    candidates = (preferred,) if preferred else DEFAULT_FONT_CANDIDATES
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def build_events(
    words: list[dict], clip_start: float = 0.0, clip_end: float | None = None,
    max_words: int = 3, max_chars: int = 18,
) -> list[dict]:
    """Group words into phrases, each with its own word timings."""
    selected = [
        w
        for w in words
        if float(w["start"]) >= clip_start
        and (clip_end is None or float(w["end"]) <= clip_end)
    ]
    events: list[dict] = []
    current: list[dict] = []
    length = 0
    for word in selected:
        text = str(word["word"])
        if current and (len(current) >= max_words or length + len(text) + 1 > max_chars):
            events.append(_event(current, clip_start))
            current, length = [], 0
        current.append(word)
        length += len(text) + 1
    if current:
        events.append(_event(current, clip_start))
    return events


def _event(group: list[dict], clip_start: float) -> dict:
    return {
        "start": float(group[0]["start"]) - clip_start,
        "end": float(group[-1]["end"]) - clip_start,
        "words": [
            {
                "text": str(w["word"]),
                "start": float(w["start"]) - clip_start,
                "end": float(w["end"]) - clip_start,
            }
            for w in group
        ],
    }


def state_at(events: list[dict], t: float) -> tuple[int, int] | None:
    """Which phrase is showing at time t, and which word inside it is active."""
    for index, event in enumerate(events):
        if event["start"] <= t < event["end"]:
            for word_index, word in enumerate(event["words"]):
                if word["start"] <= t < word["end"]:
                    return index, word_index
            return index, -1
    return None


def _load_font(size: int, path: str | None = None):
    from PIL import ImageFont

    chosen = font_path(path)
    if chosen:
        try:
            return ImageFont.truetype(chosen, size)
        except Exception:
            pass
    return ImageFont.load_default(size)


def _centered(draw, text: str, font, y: int, width: int) -> int:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    x = (width - (right - left)) // 2 - left
    draw.text((x, y), text, font=font)
    return y


def _draw_phrase(image, event: dict, active_word: int, font, width: int, height: int) -> None:
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    parts = []
    for index, word in enumerate(event["words"]):
        parts.append((word["text"], index == active_word))
    full = " ".join(text for text, _ in parts)
    left, top, right, bottom = draw.textbbox((0, 0), full, font=font)
    text_width = right - left
    x = (width - text_width) // 2 - left
    y = (height - (bottom - top)) // 2 - top

    cursor = x
    for text, active in parts:
        w_left, w_top, w_right, w_bottom = draw.textbbox((0, 0), text, font=font)
        w_width = w_right - w_left
        color = (255, 214, 0, 255) if active else (255, 255, 255, 255)
        draw.text(
            (cursor, y),
            text,
            font=font,
            fill=color,
            stroke_width=6,
            stroke_fill=(0, 0, 0, 255),
        )
        cursor += w_width + draw.textlength(" ", font=font)


def render_caption_layer(
    events: list[dict],
    out_path: str,
    duration: float,
    width: int = 1080,
    height: int = CAPTION_HEIGHT,
    fps: int = 30,
    font_size: int = 72,
    font: str | None = None,
) -> str:
    """A transparent video with the captions on it."""
    return _render_layer(
        out_path,
        duration,
        width,
        height,
        fps,
        painter=lambda image, t: _paint_captions(image, events, t, font_size, font, width, height),
    )


def _paint_captions(image, events, t, font_size, font_path, width, height) -> None:
    state = state_at(events, t)
    if state is None:
        return
    index, word_index = state
    from PIL import ImageFont

    font = _load_font(font_size, font_path)
    _draw_phrase(image, events[index], word_index, font, width, height)


def render_hook_layer(
    hook: str,
    out_path: str,
    duration: float = 3.5,
    show_for: float = 3.5,
    width: int = 1080,
    height: int = HOOK_HEIGHT,
    fps: int = 30,
    font_size: int = 76,
    font: str | None = None,
) -> str:
    """A transparent video with the hook on it, for the first seconds."""
    text = (hook or "").strip().upper()
    if not text:
        return _render_layer(out_path, duration, width, height, fps, painter=lambda image, t: None)

    from PIL import ImageDraw

    lines, chosen_font = _fit_hook(text, width, font_size, font)

    def painter(image, t):
        if t >= show_for:
            return
        draw = ImageDraw.Draw(image)
        padding = 26
        line_height = chosen_font.getbbox("Ag")[3] - chosen_font.getbbox("Ag")[1]
        gap = 8
        total = line_height * len(lines) + gap * (len(lines) - 1)
        y = (height - total) // 2
        for line in lines:
            left, top, right, bottom = draw.textbbox((0, 0), line, font=chosen_font)
            x = (width - (right - left)) // 2 - left
            draw.rounded_rectangle(
                [x - padding, y - padding, x + (right - left) + padding, y + (bottom - top) + padding],
                radius=16,
                fill=(0, 0, 0, 170),
            )
            draw.text(
                (x, y),
                line,
                font=chosen_font,
                fill=(255, 214, 0, 255),
                stroke_width=5,
                stroke_fill=(0, 0, 0, 255),
            )
            y += line_height + gap

    return _render_layer(out_path, duration, width, height, fps, painter=painter)


def _fit_hook(text: str, width: int, font_size: int, font: str | None):
    """Wrap the hook and shrink it until it fits inside the safe margins."""
    from PIL import ImageDraw, Image

    draw = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    available = width - 2 * SAFE_MARGIN

    size = font_size
    while size >= 34:
        chosen = _load_font(size, font)
        lines = _wrap(text, chosen, draw, available)
        if len(lines) <= 2:
            return lines, chosen
        size -= 6
    chosen = _load_font(34, font)
    return _wrap(text, chosen, draw, available), chosen


def _wrap(text: str, chosen_font, draw, available: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=chosen_font) <= available or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _render_layer(out_path: str, duration: float, width: int, height: int, fps: int, painter) -> str:
    """Render frames into a transparent video, one paint per visible state."""
    from PIL import Image

    total_frames = max(1, int(round(duration * fps)))
    if os.path.exists(out_path):
        os.remove(out_path)

    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{width}x{height}", "-r", str(fps),
        "-i", "-",
        "-c:v", "qtrle", "-pix_fmt", "rgba",
        out_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        cache: dict[tuple, bytes] = {}
        for frame_index in range(total_frames):
            t = frame_index / fps
            key = (round(t, 2),)
            image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            painter(image, t)
            data = image.tobytes()
            proc.stdin.write(data)
    finally:
        proc.stdin.close()
        stderr = proc.stderr.read().decode("utf-8", "replace")
        code = proc.wait()
    if code != 0:
        raise RuntimeError(f"caption layer render failed: {stderr[-400:]}")
    return out_path


def clean_temp(*paths: str) -> None:
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
