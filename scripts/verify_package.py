"""Structural check of the skill package.

Run: python3 scripts/verify_package.py
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_FILES = [
    "SKILL.md",
    "skill.json",
    "README.md",
    "LICENSE",
    "NOTICE",
    "bin/gta6-clipper",
    "scripts/setup.sh",
    "pyproject.toml",
]

REQUIRED_MODULES = [
    "src/gta6clipper/cli.py",
    "src/gta6clipper/pipeline.py",
    "src/gta6clipper/fetch.py",
    "src/gta6clipper/transcribe.py",
    "src/gta6clipper/loudness.py",
    "src/gta6clipper/moments.py",
    "src/gta6clipper/rubric.py",
    "src/gta6clipper/llm.py",
    "src/gta6clipper/captions.py",
    "src/gta6clipper/ffmpeg.py",
    "src/gta6clipper/facecam.py",
    "src/gta6clipper/render.py",
    "src/gta6clipper/find_streams.py",
    "src/gta6clipper/chat.py",
    "src/gta6clipper/config.py",
]


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    for relative in REQUIRED_FILES + REQUIRED_MODULES:
        path = os.path.join(ROOT, relative)
        if not os.path.isfile(path):
            fail(f"missing {relative}")

    skill_md = open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read()
    if not skill_md.startswith("---"):
        fail("SKILL.md has no frontmatter")
    frontmatter = skill_md.split("---", 2)[1]
    if not re.search(r"^name:\s*\S", frontmatter, re.M):
        fail("SKILL.md frontmatter has no name")
    if not re.search(r"^description:\s*\S", frontmatter, re.M):
        fail("SKILL.md frontmatter has no description")

    manifest = json.load(open(os.path.join(ROOT, "skill.json"), encoding="utf-8"))
    for field in ("name", "version", "description", "entrypoint", "requirements"):
        if field not in manifest:
            fail(f"skill.json missing {field}")

    for script in ("bin/gta6-clipper", "scripts/setup.sh"):
        if not os.access(os.path.join(ROOT, script), os.X_OK):
            fail(f"{script} is not executable")

    body = skill_md.split("---", 2)[2]
    for required in ("setup", "clip", "auto-clip", "doctor"):
        if required not in body:
            fail(f"SKILL.md never mentions {required}")

    print("PACKAGE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
