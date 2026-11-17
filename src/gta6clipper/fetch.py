"""Fetching: yt-dlp wrappers for audio, metadata, video sections and live search."""
from __future__ import annotations

import json
import os
import shutil
import subprocess

YTDLP = shutil.which("yt-dlp") or "yt-dlp"


def _base(cookies: str | None = None) -> list[str]:
    cmd = [YTDLP, "--no-progress", "--no-warnings"]
    if cookies:
        cmd += ["--cookies-from-browser", cookies]
    return cmd


def audio_command(url: str, outdir: str, cookies: str | None = None) -> list[str]:
    """Audio only. A four hour stream is a few hundred MB, not a few GB."""
    return _base(cookies) + [
        "-f", "ba",
        "--extract-audio",
        "--audio-format", "m4a",
        "--audio-quality", "0",
        "-o", os.path.join(outdir, "audio.%(ext)s"),
        url,
    ]


def video_section_command(
    url: str, start: float, end: float, outdir: str, cookies: str | None = None
) -> list[str]:
    """Only the bytes of one time range."""
    return _base(cookies) + [
        "-f", "bv*+ba/b",
        "--download-sections", f"*{start:.1f}-{end:.1f}",
        "--force-keyframes-at-cuts",
        "-o", os.path.join(outdir, "segment.%(ext)s"),
        url,
    ]


def metadata_command(url: str, cookies: str | None = None) -> list[str]:
    return _base(cookies) + ["--dump-single-json", "--no-playlist", url]


def search_command(query: str, limit: int = 20, cookies: str | None = None) -> list[str]:
    # --dump-json (not --flat-playlist): a flat entry has no live status and no
    # viewer count, which is exactly what the ranking needs.
    return _base(cookies) + [
        "--dump-json",
        f"ytsearch{limit}:{query}",
    ]


def _direct_stream_url(url: str, cookies: str | None = None) -> str:
    """Resolve a live stream URL to a direct playable URL via yt-dlp."""
    proc = run(_base(cookies) + ["--get-url", url], timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp could not resolve stream URL: {proc.stderr.strip()[:400]}")
    # yt-dlp may output multiple lines (formats); take the first non-empty one
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line and line.startswith(("http://", "https://")):
            return line
    raise RuntimeError(f"yt-dlp returned no playable URL: {proc.stdout[:200]}")


def record_stream_live_command(
    stream_url: str, duration_seconds: int, outdir: str
) -> list[str]:
    """Build an ffmpeg command to record a live stream for a fixed duration.

    Records both video and audio as MP4, then stops. Safe for ongoing streams.
    """
    return [
        "ffmpeg", "-y", "-v", "error",
        "-i", stream_url,
        "-t", str(duration_seconds),
        "-c", "copy",  # copy both video and audio without re-encoding
        os.path.join(outdir, "live_stream.mp4"),
    ]


def record_stream_live(
    url: str, duration_seconds: int, outdir: str, cookies: str | None = None
) -> str:
    """Record ``duration_seconds`` of a live stream as MP4.

    Resolves the stream URL via yt-dlp (cookies applied there), then records
    with ffmpeg for the fixed duration. Returns the path to the MP4 file.
    """
    os.makedirs(outdir, exist_ok=True)
    stream_url = _direct_stream_url(url, cookies)
    proc = run(record_stream_live_command(stream_url, duration_seconds, outdir))
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg live recording failed: {proc.stderr.strip()[:400]}"
        )
    out_path = os.path.join(outdir, "live_stream.mp4")
    if not os.path.exists(out_path):
        raise RuntimeError("ffmpeg finished but no live stream file appeared")
    return out_path


# Backwards-compatible alias
record_audio_live_command = record_stream_live_command
record_audio_live = record_stream_live


def run(cmd: list[str], timeout: int = 7200) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def parse_metadata(info: dict) -> dict:
    """The fields the pipeline cares about, with safe defaults."""
    return {
        "id": info.get("id", ""),
        "title": info.get("title", "") or "",
        "channel": info.get("channel") or info.get("uploader") or "",
        "channel_url": info.get("channel_url", "") or "",
        "duration": float(info.get("duration") or 0),
        "is_live": bool(info.get("is_live")),
        "live_status": info.get("live_status", "") or "",
        "view_count": int(info.get("view_count") or 0),
        "webpage_url": info.get("webpage_url", "") or "",
        "thumbnail": info.get("thumbnail", "") or "",
        "upload_date": info.get("upload_date", "") or "",
    }


def fetch_metadata(url: str, cookies: str | None = None) -> dict:
    proc = run(metadata_command(url, cookies), timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp metadata failed: {proc.stderr.strip()[:400]}")
    try:
        return parse_metadata(json.loads(proc.stdout))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"yt-dlp returned unreadable metadata: {exc}") from exc


def fetch_audio(url: str, outdir: str, cookies: str | None = None) -> str:
    os.makedirs(outdir, exist_ok=True)
    proc = run(audio_command(url, outdir, cookies))
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp audio download failed: {proc.stderr.strip()[:400]}")
    for name in sorted(os.listdir(outdir)):
        if name.startswith("audio.") and not name.endswith((".part", ".ytdl")):
            return os.path.join(outdir, name)
    raise RuntimeError("yt-dlp finished but no audio file appeared")


def fetch_video_section(
    url: str, start: float, end: float, outdir: str, cookies: str | None = None
) -> str:
    os.makedirs(outdir, exist_ok=True)
    proc = run(video_section_command(url, start, end, outdir, cookies))
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp section download failed: {proc.stderr.strip()[:400]}")
    for name in sorted(os.listdir(outdir)):
        if name.startswith("segment.") and not name.endswith((".part", ".ytdl")):
            return os.path.join(outdir, name)
    raise RuntimeError("yt-dlp finished but no segment file appeared")


def search_live(query: str, limit: int = 20, cookies: str | None = None) -> list[dict]:
    """Live streams matching a query, biggest first."""
    proc = run(search_command(query, limit, cookies), timeout=600)
    entries: list[dict] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not entries:
        raise RuntimeError(f"yt-dlp search failed: {proc.stderr.strip()[:400]}")
    # A single age-restricted result makes yt-dlp exit non-zero while the other
    # results are still on stdout, so the exit code alone is not a failure here.
    out = []
    for entry in entries:
        if not entry:
            continue
        out.append(
            {
                "id": entry.get("id", ""),
                "title": entry.get("title", "") or "",
                "channel": entry.get("channel") or entry.get("uploader") or "",
                "is_live": bool(entry.get("is_live")),
                "live_status": entry.get("live_status", "") or "",
                "view_count": int(entry.get("view_count") or 0),
                "duration": float(entry.get("duration") or 0),
                "url": entry.get("webpage_url") or f"https://www.youtube.com/watch?v={entry.get('id', '')}",
            }
        )
    return out
