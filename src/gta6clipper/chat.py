"""YouTube chat velocity: the second signal, when it is available.

Chat is a useful tell: when a few thousand people start typing at the same
second, something happened. It needs an extra package and only works for
YouTube, so it is optional. Without it the pipeline still runs on loudness and
the LLM's read of the transcript.
"""
from __future__ import annotations

import collections


def chat_counts(url: str, video_id: str = "") -> list[tuple[float, int]]:
    """Messages per second over the stream. Empty when the route is unavailable."""
    try:
        from youtube_chat_downloader import YouTubeChatDownloader
    except ImportError:
        return []

    try:
        downloader = YouTubeChatDownloader()
        generator = downloader.get_live_chat(url=video_id or url)
        counts: collections.Counter = collections.Counter()
        base = None
        for message in generator:
            timestamp = getattr(message, "timestamp", None)
            if timestamp is None:
                continue
            if base is None:
                base = timestamp
            seconds = (timestamp - base).total_seconds()
            counts[round(seconds)] += 1
    except Exception:
        return []

    if not counts:
        return []
    return sorted(counts.items())


def chat_peaks(counts: list[tuple[float, int]], threshold: float = 3.0, window_s: float = 10.0):
    """Seconds where chat moved faster than its own average."""
    from .moments import Candidate

    if not counts:
        return []
    values = [c for _, c in counts]
    average = sum(values) / len(values)
    if average <= 0:
        return []
    peaks: list[Candidate] = []
    current: list[tuple[float, int]] = []
    for second, value in counts:
        if value > average * threshold:
            current.append((second, value))
        elif current:
            peaks.append(_as_candidate(current))
            current = []
    if current:
        peaks.append(_as_candidate(current))
    return peaks


def _as_candidate(points: list[tuple[float, int]]) -> Candidate:
    start = points[0][0]
    end = points[-1][0] + 1.0
    score = max(v for _, v in points) / max(1, sum(v for _, v in points) / len(points))
    return Candidate(start=start, end=end, source="chat", score=float(score))
