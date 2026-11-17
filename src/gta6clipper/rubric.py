"""The rubric: what makes a clip worth posting, and what to throw away."""
from __future__ import annotations

MOMENT_TYPES = (
    "first_reaction",
    "crazy_discovery",
    "freakout",
    "funny_fail",
    "hot_take",
)

MAX_CLIP_SECONDS = 90
MIN_CLIP_SECONDS = 6
MIN_HASHTAGS = 3
MAX_HASHTAGS = 8
MAX_HOOK_CHARS = 80
MAX_TITLE_CHARS = 100

REQUIRED_FIELDS = ("start", "end", "type", "score", "hook", "title", "caption", "hashtags")


def validate_moment(moment: dict) -> list[str]:
    """Everything wrong with a proposed clip. An empty list means it is usable."""
    errors: list[str] = []
    if not isinstance(moment, dict):
        return ["moment is not an object"]

    for field in REQUIRED_FIELDS:
        if field not in moment:
            errors.append(f"missing field: {field}")
    if errors:
        return errors

    start, end = moment["start"], moment["end"]
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        errors.append("start and end must be numbers")
        return errors
    start, end = float(start), float(end)
    if start < 0:
        errors.append("start is negative")
    if end <= start:
        errors.append("end must be after start")
    elif end - start > MAX_CLIP_SECONDS:
        errors.append(f"clip longer than {MAX_CLIP_SECONDS}s")
    elif end - start < MIN_CLIP_SECONDS:
        errors.append(f"clip shorter than {MIN_CLIP_SECONDS}s")

    if moment["type"] not in MOMENT_TYPES:
        errors.append(f"unknown type: {moment['type']}")

    score = moment["score"]
    if not isinstance(score, (int, float)) or not 0 <= float(score) <= 100:
        errors.append("score must be between 0 and 100")

    hook = moment["hook"]
    if not isinstance(hook, str) or not hook.strip():
        errors.append("hook is empty")
    elif len(hook) > MAX_HOOK_CHARS:
        errors.append(f"hook longer than {MAX_HOOK_CHARS} characters")

    title = moment["title"]
    if not isinstance(title, str) or not title.strip():
        errors.append("title is empty")
    elif len(title) > MAX_TITLE_CHARS:
        errors.append(f"title longer than {MAX_TITLE_CHARS} characters")

    if not isinstance(moment["caption"], str):
        errors.append("caption must be text")

    hashtags = moment["hashtags"]
    if not isinstance(hashtags, list):
        errors.append("hashtags must be a list")
    else:
        if not MIN_HASHTAGS <= len(hashtags) <= MAX_HASHTAGS:
            errors.append(f"needs {MIN_HASHTAGS}-{MAX_HASHTAGS} hashtags")
        if any(not isinstance(h, str) or not h.startswith("#") for h in hashtags):
            errors.append("hashtags must start with #")

    if moment.get("needs_context") is True:
        errors.append("needs context to make sense")
    if moment.get("starts_with_filler") is True:
        errors.append("starts with filler")
    return errors


def build_scoring_prompt(transcript_text: str, window_start: float, window_end: float) -> str:
    """The instruction the LLM gets for one window of the stream."""
    types = ", ".join(MOMENT_TYPES)
    return f"""You are selecting clips from a livestream VOD for short-form video (YouTube Shorts, TikTok, Reels).

Read the transcript excerpt below and find the moments people would clip and share.

Transcript excerpt ({window_start:.0f}s to {window_end:.0f}s of the stream):

{transcript_text}

Only these moment types count:
- first_reaction: the very first reaction to something, said out loud
- crazy_discovery: finding something nobody expected
- freakout: losing control, screaming, going completely silent in shock
- funny_fail: something going hilariously wrong
- hot_take: a strong opinion about the game that sparks argument

Be HARSH. Reject a moment when:
- it needs context from earlier in the stream to make sense
- it starts with filler ("uh", "so yeah", "wait hold on", "anyway")
- it is just talking, setup, or dead air
- it would not be funny, shocking or arguable as a standalone clip

Score each moment 0-100. Below 70 is not worth posting. Be harsh with the score too.

A clip must run 15 to 45 seconds: the reaction plus the beat that pays it off.
Too short and it has no payoff; too long and it drags.

Return ONLY a JSON array, no commentary. Each element:
{{
  "start": <seconds into the stream, number>,
  "end": <seconds into the stream, number>,
  "type": "<one of: {types}>",
  "score": <number 0-100>,
  "hook": "<3 to 8 words on screen, the promise of the clip>",
  "title": "<short title for the post, under 100 characters>",
  "caption": "<one or two sentences for the post caption>",
  "hashtags": ["#GTA6", "#Shorts", "#Gaming"],
  "needs_context": <true or false>,
  "starts_with_filler": <true or false>
}}

Seconds are absolute times in the original stream, not times inside this excerpt.
Return [] if nothing in this excerpt is worth clipping.
"""
