"""Scoring check: the rubric and the model plumbing, offline.

Run: python3 scripts/verify_scoring.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

# The clipper's Python dependencies live in the virtualenv setup created.
try:
    import numpy  # noqa: F401
except ImportError:
    venv_python = os.path.expanduser("~/.cache/gta6-clipper/venv/bin/python")
    if os.path.exists(venv_python):
        os.execv(venv_python, [venv_python, os.path.abspath(__file__)] + sys.argv[1:])
    raise

from gta6clipper import llm, moments, rubric  # noqa: E402

TRANSCRIPT = [
    {"word": "He", "start": 1.0, "end": 1.3},
    {"word": "cannot", "start": 1.3, "end": 1.7},
    {"word": "believe", "start": 1.7, "end": 2.1},
    {"word": "what", "start": 2.1, "end": 2.4},
    {"word": "just", "start": 2.4, "end": 2.7},
    {"word": "happened", "start": 2.7, "end": 3.2},
]

GOOD = {
    "start": 1.0,
    "end": 40.0,
    "type": "freakout",
    "score": 88,
    "hook": "He was NOT ready for this",
    "title": "Streamer loses it",
    "caption": "He genuinely did not see that coming.",
    "hashtags": ["#GTA6", "#Shorts", "#Gaming"],
    "needs_context": False,
    "starts_with_filler": False,
}

NEEDS_CONTEXT = dict(GOOD, needs_context=True, hook="Context dependent")
LOW_SCORE = dict(GOOD, score=20, hook="Boring moment")


class StubBackend(llm.Backend):
    name = "stub"

    def __init__(self, response: str):
        self.response = response

    def command(self, prompt: str) -> list[str]:
        return ["stub"]

    def complete(self, prompt: str, timeout: int = 900) -> str:
        return self.response


def main() -> int:
    failures = []

    windows = moments.windows_from_words(TRANSCRIPT, window_minutes=12)
    if len(windows) != 1:
        failures.append(f"expected one transcript window, got {len(windows)}")

    prompt = rubric.build_scoring_prompt(windows[0].text, windows[0].start, windows[0].end)
    for token in ("first_reaction", "freakout", "needs_context", "JSON", "cannot"):
        if token not in prompt:
            failures.append(f"prompt is missing {token!r}")

    raw = json.dumps([GOOD, NEEDS_CONTEXT, LOW_SCORE])
    kept, errors = llm.parse_moments(raw)
    if len(kept) != 2:
        failures.append(f"expected 2 valid moments (score filtering happens later), got {len(kept)}")
    if not errors:
        failures.append("expected the context-dependent moment to be reported")

    stub = StubBackend("```json\n" + raw + "\n```")
    if "```json" not in stub.complete(""):
        failures.append("stub backend did not return its response")

    from gta6clipper.pipeline import score_windows

    selected, problems = score_windows(windows, stub, min_score=70)
    if len(selected) != 1:
        failures.append(f"expected 1 selected moment, got {len(selected)}")
    if selected and selected[0]["hook"] != GOOD["hook"]:
        failures.append("the wrong moment was selected")
    if not problems:
        failures.append("expected the rejected moments to be reported")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("SCORING OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
