"""ffmpeg filter graphs for the vertical output."""
from __future__ import annotations

OUT_WIDTH = 1080
OUT_HEIGHT = 1920

FACECAM_WIDTH = 900
FACECAM_HEIGHT = 506
FACECAM_TOP = 40
FACECAM_GAP = 60


def loudnorm_filter(target_lufs: int = -14, true_peak: float = -1.5, lra: float = 11.0) -> str:
    """Platform-standard loudness for short-form video."""
    return f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}"


def vertical_filtergraph(
    src_w: int,
    src_h: int,
    facecam_box: tuple[int, int, int, int] | None = None,
    out_w: int = OUT_WIDTH,
    out_h: int = OUT_HEIGHT,
) -> str:
    """Gameplay below, facecam on top, blurred backdrop filling the frame.

    A 16:9 stream on a 9:16 frame loses most of its width if it is simply
    cropped, so the gameplay is centred whole over a blurred, scaled copy of
    itself. The facecam sits above it, where a thumb never covers it.
    """
    backdrop = (
        f"[0:v]split=3[bg][gm][fc];"
        f"[bg]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
        f"crop={out_w}:{out_h},gblur=sigma=40[bgv];"
        f"[gm]scale={out_w}:-2[gmv]"
    )

    if facecam_box:
        x, y, w, h = facecam_box
        gameplay_y = FACECAM_TOP + FACECAM_HEIGHT + FACECAM_GAP + 40
        graph = (
            f"{backdrop};"
            f"[fc]crop={w}:{h}:{x}:{y},scale={FACECAM_WIDTH}:{FACECAM_HEIGHT}[fcv];"
            f"[bgv][gmv]overlay=(W-w)/2:{gameplay_y}[tmp];"
            f"[tmp][fcv]overlay=(W-w)/2:{FACECAM_TOP}[outv]"
        )
    else:
        graph = f"{backdrop};[bgv][gmv]overlay=(W-w)/2:(H-h)/2[outv]"

    return graph + f";[outv]scale={out_w}:{out_h},format=yuv420p[vout]"


def render_command(
    video: str,
    output: str,
    filtergraph: str,
    subtitles: list[str] | None = None,
    duration: float | None = None,
) -> list[str]:
    """The full ffmpeg invocation for one clip (video and audio in the same file)."""
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if duration:
        cmd += ["-t", f"{duration:.2f}"]
    cmd += ["-i", video]

    chain = filtergraph
    subs = subtitles or []
    for index, path in enumerate(subs):
        source = "vout" if index == 0 else f"sub{index - 1}"
        escaped = path.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
        chain += f";[{source}]subtitles='{escaped}'[sub{index}]"
    final = f"sub{len(subs) - 1}" if subs else "vout"

    cmd += [
        "-filter_complex", chain,
        "-map", f"[{final}]",
        "-map", "0:a",
        "-af", loudnorm_filter(),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-r", "30",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output,
    ]
    return cmd
