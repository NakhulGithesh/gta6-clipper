"""Candidate moments: transcript windows plus loudness and chat signals."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Candidate:
    start: float
    end: float
    source: str = "audio"  # audio | chat | both
    score: float = 0.0


@dataclass
class Window:
    start: float
    end: float
    text: str = ""
    candidates: list[Candidate] = field(default_factory=list)


def _timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def windows_from_words(words: list[dict], window_minutes: int = 12) -> list[Window]:
    """Split a transcript into fixed reading windows.

    The LLM reads the stream in chunks, the same way a person would: a window
    that is too small loses the setup of a reaction, a window that is too big
    loses the thread.
    """
    if not words:
        return []
    span = float(window_minutes) * 60.0
    total_end = float(words[-1]["end"])
    out: list[Window] = []
    start = 0.0
    while start < total_end:
        end = min(start + span, total_end)
        chunk = [w for w in words if float(w["end"]) > start and float(w["start"]) < end]
        lines = [f"[{_timestamp(float(w['start']))}] {w['word']}" for w in chunk]
        out.append(Window(start=start, end=end, text="\n".join(lines)))
        start = end
    return out


def merge_sources(
    audio: list[Candidate], chat: list[Candidate], overlap_s: float = 5.0
) -> list[Candidate]:
    """Merge audio peaks and chat spikes that describe the same moment."""
    items = sorted([*audio, *chat], key=lambda c: c.start)
    out: list[Candidate] = []
    for item in items:
        if out and item.start - out[-1].end <= overlap_s:
            prev = out[-1]
            prev.end = max(prev.end, item.end)
            prev.score = max(prev.score, item.score)
            if prev.source != item.source:
                prev.source = "both"
        else:
            out.append(Candidate(item.start, item.end, item.source, item.score))
    return out


def dedupe(candidates: list[Candidate], min_gap_s: float = 10.0) -> list[Candidate]:
    """Keep the strongest of any group of overlapping candidates."""
    ordered = sorted(candidates, key=lambda c: -c.score)
    kept: list[Candidate] = []
    for cand in ordered:
        if all(
            cand.end + min_gap_s <= other.start or other.end + min_gap_s <= cand.start
            for other in kept
        ):
            kept.append(cand)
    kept.sort(key=lambda c: c.start)
    return kept
