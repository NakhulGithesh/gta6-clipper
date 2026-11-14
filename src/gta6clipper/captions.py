"""ASS subtitles: word-by-word captions and the hook title."""
from __future__ import annotations

import re

DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,6,2,2,70,70,260,1
Style: Hook,Arial,{hook_font_size},&H0000FFFF,&H000000FF,&H00000000,&HC0000000,-1,0,0,0,100,100,0,0,3,8,0,8,60,60,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

_TAG = re.compile(r"[{}\\]")


def _clean(text: str) -> str:
    return _TAG.sub("", text).strip()


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _group(words: list[dict], max_words: int, max_chars: int) -> list[list[dict]]:
    groups: list[list[dict]] = []
    current: list[dict] = []
    length = 0
    for word in words:
        text = str(word["word"])
        if current and (len(current) >= max_words or length + len(text) + 1 > max_chars):
            groups.append(current)
            current, length = [], 0
        current.append(word)
        length += len(text) + 1
    if current:
        groups.append(current)
    return groups


def words_to_ass(
    words: list[dict],
    clip_start: float = 0.0,
    clip_end: float | None = None,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    font_size: int = 64,
    max_words: int = 3,
    max_chars: int = 18,
) -> str:
    """Captions that highlight one word at a time.

    Karaoke tags do the highlighting inside the subtitle renderer, so the text
    stays readable at any frame rate and no per-word re-render is needed.
    """
    header = HEADER.format(width=width, height=height, font_size=font_size, hook_font_size=72)
    selected = [
        w
        for w in words
        if float(w["start"]) >= clip_start
        and (clip_end is None or float(w["end"]) <= clip_end)
    ]
    if not selected:
        return header

    lines = [header]
    for group in _group(selected, max_words, max_chars):
        start = float(group[0]["start"]) - clip_start
        end = float(group[-1]["end"]) - clip_start
        if end <= start:
            end = start + 0.2
        parts = []
        for word in group:
            dur = max(0.05, float(word["end"]) - float(word["start"]))
            parts.append("{\\k%d}%s" % (int(round(dur * 100)), _clean(str(word["word"]))))
        text = " ".join(parts)
        lines.append(
            "Dialogue: 0,%s,%s,Caption,,0,0,0,,%s" % (_ass_time(start), _ass_time(end), text)
        )
    return "\n".join(lines) + "\n"


def hook_ass(
    hook: str,
    duration: float = 3.5,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    top: int = 430,
    font_size: int = 72,
) -> str:
    """The on-screen promise of the clip, shown over the first seconds."""
    header = HEADER.format(width=width, height=height, font_size=font_size, hook_font_size=font_size)
    text = _clean(hook).upper()
    if not text:
        return header
    body = (
        "Dialogue: 0,%s,%s,Hook,,0,0,0,,{\\fad(120,120)}%s"
        % (_ass_time(0), _ass_time(duration), text)
    )
    return header + body + "\n"
