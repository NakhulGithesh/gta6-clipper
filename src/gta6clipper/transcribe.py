"""Transcription: local whisper.cpp, with YouTube captions as the fallback."""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess

WHISPER_MODELS = {
    "tiny": "ggml-tiny.bin",
    "base": "ggml-base.bin",
    "small": "ggml-small.bin",
    "medium": "ggml-medium.bin",
    "large-v3-turbo": "ggml-large-v3-turbo.bin",
}

MODEL_URLS = {
    "ggml-tiny.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
    "ggml-base.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
    "ggml-small.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
    "ggml-medium.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin",
    "ggml-large-v3-turbo.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin",
}


def parse_whisper_json(payload: dict) -> list[dict]:
    """whisper.cpp JSON output -> words with timings."""
    words: list[dict] = []
    segments = payload.get("transcription") or payload.get("segments") or []
    for segment in segments:
        tokens = segment.get("tokens")
        if tokens:
            for token in tokens:
                text = (token.get("text") or "").strip()
                if not text or not text.isalnum() and not any(c.isalnum() for c in text):
                    continue
                offsets = token.get("offsets") or {}
                if "from" not in offsets or "to" not in offsets:
                    continue
                words.append(
                    {
                        "word": text,
                        "start": float(offsets["from"]) / 1000.0,
                        "end": float(offsets["to"]) / 1000.0,
                    }
                )
            continue
        text = (segment.get("text") or "").strip()
        if not text:
            continue
        offsets = segment.get("offsets") or {}
        start = float(offsets.get("from", 0)) / 1000.0
        end = float(offsets.get("to", 0)) / 1000.0
        parts = text.split()
        if not parts:
            continue
        step = max(0.05, (end - start) / len(parts))
        for i, part in enumerate(parts):
            words.append({"word": part, "start": start + i * step, "end": start + (i + 1) * step})
    return words


_VTT_TIME = re.compile(
    r"(\d{2}:)?(\d{2}):(\d{2})[.,](\d{3})\s+-->\s+(\d{2}:)?(\d{2}):(\d{2})[.,](\d{3})"
)


def _vtt_seconds(match: re.Match) -> tuple[float, float]:
    h1 = int(match.group(1)[:-2] or 0) if match.group(1) else 0
    h2 = int(match.group(5)[:-2] or 0) if match.group(5) else 0
    start = h1 * 3600 + int(match.group(2)) * 60 + int(match.group(3)) + int(match.group(4)) / 1000
    end = h2 * 3600 + int(match.group(6)) * 60 + int(match.group(7)) + int(match.group(8)) / 1000
    return start, end


def parse_vtt(text: str) -> list[dict]:
    """WebVTT/SRT cues -> words, with the cue's time spread over its words."""
    words: list[dict] = []
    blocks = re.split(r"\n\s*\n", text.strip())
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        timing_index = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if timing_index is None:
            continue
        match = _VTT_TIME.search(lines[timing_index])
        if not match:
            continue
        start, end = _vtt_seconds(match)
        content = " ".join(lines[timing_index + 1 :])
        content = re.sub(r"<[^>]+>", "", content)
        parts = [p for p in content.split() if p]
        if not parts:
            continue
        step = max(0.05, (end - start) / len(parts))
        for i, part in enumerate(parts):
            words.append({"word": part, "start": start + i * step, "end": start + (i + 1) * step})
    return words


def parse_srt(text: str) -> list[dict]:
    return parse_vtt(text)


def transcript_text(words: list[dict]) -> str:
    """Timestamped lines, the form the LLM reads."""
    lines = []
    for word in words:
        seconds = float(word["start"])
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        lines.append(f"[{h:02d}:{m:02d}:{s:06.3f}] {word['word']}")
    return "\n".join(lines)


def whisper_binary() -> str | None:
    for name in ("whisper-cli", "main", "whisper-cpp"):
        found = shutil.which(name)
        if found:
            return found
    return None


def model_path(model: str = "large-v3-turbo", cache_dir: str | None = None) -> str:
    from . import config

    cache = cache_dir or config.CACHE_DIR
    return os.path.join(config.MODEL_DIR, WHISPER_MODELS.get(model, WHISPER_MODELS["large-v3-turbo"]))


def to_wav(audio_path: str, out_path: str, sample_rate: int = 16000) -> str:
    """16 kHz mono wav. whisper.cpp reads wav, not the container yt-dlp gives us."""
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-i", audio_path,
        "-ar", str(sample_rate), "-ac", "1", "-c:a", "pcm_s16le", out_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg wav conversion failed: {proc.stderr.strip()[:300]}")
    return out_path


def transcribe_whisper(audio_path: str, outdir: str, model: str = "large-v3-turbo") -> list[dict]:
    """Run whisper.cpp locally. Nothing leaves the machine."""
    binary = whisper_binary()
    if not binary:
        raise RuntimeError("whisper.cpp is not installed (run: gta6-clipper setup)")
    weights = model_path(model)
    if not os.path.exists(weights):
        raise RuntimeError(f"whisper model missing: {weights} (run: gta6-clipper setup)")

    os.makedirs(outdir, exist_ok=True)
    wav = os.path.join(outdir, "audio16k.wav")
    to_wav(audio_path, wav)
    stem = os.path.join(outdir, "whisper")
    cmd = [binary, "-m", weights, "-f", wav, "-oj", "-of", stem, "-np"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    if proc.returncode != 0:
        raise RuntimeError(f"whisper.cpp failed: {proc.stderr.strip()[:400]}")
    produced = glob.glob(stem + "*.json")
    if not produced:
        raise RuntimeError("whisper.cpp produced no JSON output")
    with open(produced[0], "r", encoding="utf-8") as handle:
        return parse_whisper_json(json.load(handle))


def fetch_captions(url: str, outdir: str, cookies: str | None = None) -> list[dict]:
    """YouTube's own captions. Free and instant, but word timing is estimated."""
    from . import fetch

    os.makedirs(outdir, exist_ok=True)
    cmd = fetch._base(cookies) + [
        "--write-auto-subs",
        "--write-subs",
        "--sub-langs", "en.*",
        "--skip-download",
        "-o", os.path.join(outdir, "captions.%(ext)s"),
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        return []
    files = sorted(glob.glob(os.path.join(outdir, "captions*.vtt")))
    if not files:
        return []
    with open(files[0], "r", encoding="utf-8") as handle:
        return parse_vtt(handle.read())
