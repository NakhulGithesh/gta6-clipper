"""End-to-end check: a real public video becomes real clips.

Run: python3 scripts/verify_e2e.py [url]

Defaults to the video this skill was built from. The scoring backend is the
Claude CLI when it answers, otherwise a deterministic stub, so the pipeline is
exercised either way.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from gta6clipper import llm, pipeline  # noqa: E402

DEFAULT_URL = "https://www.youtube.com/watch?v=5-SDYLlGZFw"

STUB_RESPONSE = json.dumps(
    [
        {
            "start": 60.0,
            "end": 95.0,
            "type": "hot_take",
            "score": 80,
            "hook": "This changes everything",
            "title": "The take nobody expected",
            "caption": "He says the quiet part out loud.",
            "hashtags": ["#GTA6", "#Shorts", "#Gaming"],
            "needs_context": False,
            "starts_with_filler": False,
        }
    ]
)


class StubBackend(llm.Backend):
    name = "stub"

    def command(self, prompt: str) -> list[str]:
        return ["stub"]

    def complete(self, prompt: str, timeout: int = 900) -> str:
        return STUB_RESPONSE


def claude_answers() -> bool:
    if not shutil.which("claude"):
        return False
    try:
        proc = subprocess.run(
            ["claude", "-p", "Reply with exactly: OK", "--output-format", "text"],
            capture_output=True, text=True, timeout=180,
        )
    except Exception:
        return False
    return proc.returncode == 0 and "OK" in proc.stdout.upper()


def dimensions(path: str) -> tuple[int, int]:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "json", path],
        capture_output=True, text=True,
    )
    try:
        stream = json.loads(proc.stdout)["streams"][0]
        return int(stream["width"]), int(stream["height"])
    except Exception:
        return 0, 0


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    failures = []

    backend: llm.Backend
    if claude_answers():
        print("[e2e] scoring with the real Claude CLI")
        backend = llm.ClaudeCliBackend()
    else:
        print("[e2e] Claude CLI unavailable, scoring with the deterministic stub")
        backend = StubBackend()

    out_dir = tempfile.mkdtemp(prefix="gta6-clipper-e2e-")
    try:
        result = pipeline.clip_stream(url, out_dir=out_dir, clips=1, backend=backend)
        workdir = result["workdir"]
        clips_file = os.path.join(workdir, "clips.json")
        if not os.path.isfile(clips_file):
            failures.append("clips.json was not written")
        clips = result.get("clips") or []
        if not clips:
            failures.append("no clip was rendered")
        for clip in clips:
            path = clip["file"]
            if not os.path.isfile(path):
                failures.append(f"missing clip file {path}")
                continue
            size = os.path.getsize(path)
            if size < 20_000:
                failures.append(f"clip file is suspiciously small: {size} bytes")
            width, height = dimensions(path)
            if (width, height) != (1080, 1920):
                failures.append(f"clip is {width}x{height}, expected 1080x1920")
            post = clip.get("post_caption_file", "")
            if not post or not os.path.isfile(post):
                failures.append("post caption file is missing")
            elif "#" not in open(post, encoding="utf-8").read():
                failures.append("post caption has no hashtags")
        for artifact in ("meta.json", "transcript.json", "moments.json"):
            if not os.path.isfile(os.path.join(workdir, artifact)):
                failures.append(f"{artifact} was not written")
    except Exception as exc:
        failures.append(f"pipeline raised: {exc}")
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("E2E OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
