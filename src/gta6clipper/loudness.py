"""Loudness analysis: where the streamer got loud.

The audio of a long stream is downloaded once, decoded once, and turned into an
RMS envelope. Peaks in that envelope are candidate "he lost it" moments, so the
LLM never has to read the whole transcript looking for energy.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

import numpy as np

DEFAULT_WINDOW_SECONDS = 0.5
DEFAULT_SAMPLE_RATE = 16000


def rms(data: bytes) -> float:
    """Root mean square of 16-bit little-endian PCM, normalised to 0..1."""
    if not data:
        return 0.0
    arr = np.frombuffer(data, dtype="<i2").astype(np.float32)
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(arr))) / 32768.0)


def envelope_from_pcm(
    data: bytes, sample_rate: int = DEFAULT_SAMPLE_RATE, window_seconds: float = DEFAULT_WINDOW_SECONDS
) -> list[float]:
    """RMS per window over the whole stream."""
    if not data:
        return []
    win = max(1, int(sample_rate * window_seconds))
    arr = np.frombuffer(data, dtype="<i2")
    out: list[float] = []
    for i in range(0, arr.size, win):
        chunk = arr[i : i + win]
        if chunk.size == 0:
            break
        out.append(float(np.sqrt(np.mean(np.square(chunk.astype(np.float32)))) / 32768.0))
    return out


@dataclass
class Peak:
    start: float
    end: float
    score: float


def find_peaks(
    envelope: list[float],
    threshold_z: float = 1.5,
    min_gap_s: float = 2.0,
    top_n: int = 40,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
) -> list[Peak]:
    """Loud moments, as local maxima that stand out from the stream's own average.

    A fixed dB threshold would miss a screaming stream and trip over a quiet one.
    The score is how far above the stream's own average the window sits, so the
    same rule works on both.
    """
    if len(envelope) < 3:
        return []
    arr = np.array(envelope, dtype=float)
    spread = float(arr.std())
    z = (arr - float(arr.mean())) / (spread if spread > 1e-9 else 1.0)

    found: list[Peak] = []
    for i in range(1, len(arr) - 1):
        if z[i] < threshold_z:
            continue
        if arr[i] < arr[i - 1] or arr[i] < arr[i + 1]:
            continue
        found.append(Peak(i * window_seconds, (i + 1) * window_seconds, float(z[i])))

    found.sort(key=lambda p: -p.score)
    kept: list[Peak] = []
    for peak in found:
        if all(abs(peak.start - other.start) >= min_gap_s for other in kept):
            kept.append(peak)
        if len(kept) >= top_n:
            break
    kept.sort(key=lambda p: p.start)
    return kept


def decode_pcm(path: str, sample_rate: int = DEFAULT_SAMPLE_RATE) -> bytes:
    """Decode an audio file to 16 kHz mono signed 16-bit PCM."""
    import subprocess

    cmd = [
        "ffmpeg", "-v", "error", "-i", path,
        "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "1", "-ar", str(sample_rate),
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg decode failed: {proc.stderr.decode('utf-8', 'replace')[:400]}")
    return proc.stdout


def pcm_from_bytes(samples: list[int]) -> bytes:
    return struct.pack("<%dh" % len(samples), *samples)
