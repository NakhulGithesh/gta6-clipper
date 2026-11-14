"""Rendering one clip: facecam on top, gameplay below, captions burned in."""
from __future__ import annotations

import json
import os
import subprocess

from . import captions, config, facecam, ffmpeg


def probe_size(path: str) -> tuple[int, int]:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "json", path],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return 1920, 1080
    try:
        stream = json.loads(proc.stdout)["streams"][0]
        return int(stream["width"]), int(stream["height"])
    except Exception:
        return 1920, 1080


def write_post_caption(clip: dict, path: str) -> str:
    hashtags = " ".join(clip.get("hashtags", []))
    text = f"{clip.get('title', '').strip()}\n\n{clip.get('caption', '').strip()}\n\n{hashtags}".strip()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    return text


def render_clip(
    video_path: str,
    clip: dict,
    words: list[dict],
    out_path: str,
    workdir: str,
    facecam_model: str | None = None,
    duration: float | None = None,
) -> dict:
    """Render one clip. Returns what was produced, including what was skipped."""
    os.makedirs(workdir, exist_ok=True)
    start, end = float(clip["start"]), float(clip["end"])
    length = duration or (end - start)

    box = None
    if facecam_model and os.path.exists(facecam_model):
        box = facecam.facecam_box(video_path, facecam_model)

    width, height = probe_size(video_path)
    graph = ffmpeg.vertical_filtergraph(width, height, box)

    stem = os.path.splitext(os.path.basename(out_path))[0]
    caption_layer = os.path.join(workdir, f"{stem}-captions.mov")
    hook_layer = os.path.join(workdir, f"{stem}-hook.mov")

    events = captions.build_events(words, clip_start=start, clip_end=end)
    captions.render_caption_layer(events, caption_layer, duration=length)
    captions.render_hook_layer(clip.get("hook", ""), hook_layer, duration=length)

    cmd = ffmpeg.render_command(
        video_path,
        out_path,
        graph,
        layers=[
            (hook_layer, 0, captions.HOOK_TOP),
            (caption_layer, 0, captions.CAPTION_TOP),
        ],
        duration=length,
    )
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.strip()[-600:]}")

    post_file = os.path.splitext(out_path)[0] + ".post.txt"
    post_text = write_post_caption(clip, post_file)

    return {
        "file": out_path,
        "post_caption_file": post_file,
        "post_caption": post_text,
        "facecam": list(box) if box else None,
        "duration": round(length, 2),
        "start": start,
        "end": end,
    }
