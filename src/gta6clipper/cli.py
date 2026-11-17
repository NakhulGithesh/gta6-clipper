"""Command line entry point."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

from . import config, pipeline


def _log(message: str) -> None:
    print(f"[gta6-clipper] {message}", flush=True)


def _doctor_checks() -> list[dict]:
    checks: list[dict] = []

    def check(name, ok, detail, fix="", required=True):
        checks.append(
            {"name": name, "ok": bool(ok), "detail": detail, "fix": fix, "required": required}
        )

    for binary, install in (
        ("ffmpeg", "brew install ffmpeg"),
        ("ffprobe", "brew install ffmpeg"),
        ("yt-dlp", "brew install yt-dlp"),
    ):
        path = shutil.which(binary)
        check(binary, path, path or "missing", "" if path else install)

    whisper = transcribe_binary()
    check("whisper.cpp", whisper, whisper or "missing", "" if whisper else "brew install whisper-cpp")
    check(
        "whisper model",
        os.path.exists(config.WHISPER_MODEL),
        config.WHISPER_MODEL if os.path.exists(config.WHISPER_MODEL) else "missing",
        "" if os.path.exists(config.WHISPER_MODEL) else "gta6-clipper setup",
    )
    check(
        "facecam model",
        os.path.exists(config.FACECAM_MODEL),
        config.FACECAM_MODEL if os.path.exists(config.FACECAM_MODEL) else "missing",
        "" if os.path.exists(config.FACECAM_MODEL) else "gta6-clipper setup",
        required=False,
    )

    claude = shutil.which("claude")
    check(
        "claude cli",
        claude,
        claude or "missing",
        "" if claude else "npm i -g @anthropic-ai/claude-code",
        required=False,
    )
    opencode = shutil.which("opencode")
    check(
        "opencode cli",
        opencode,
        opencode or "missing",
        "" if opencode else "npm i -g @opencode/opencode",
        required=False,
    )

    base_url = os.environ.get("GTA6_CLIPPER_LLM_BASE_URL", "http://localhost:1234/v1")
    model = os.environ.get("GTA6_CLIPPER_LLM_MODEL", "")
    check(
        "openai endpoint",
        base_url,
        f"{base_url} ({model or '<default model>'})",
        f"set GTA6_CLIPPER_LLM_BASE_URL / GTA6_CLIPPER_LLM_MODEL (default {base_url})",
        required=False,
    )

    try:
        import cv2  # noqa: F401

        check("opencv", True, cv2.__version__)
    except ImportError:
        check("opencv", False, "missing", "pip install opencv-python")
    try:
        import numpy  # noqa: F401

        check("numpy", True, numpy.__version__)
    except ImportError:
        check("numpy", False, "missing", "pip install numpy")
    try:
        import PIL  # noqa: F401

        check("pillow", True, PIL.__version__)
    except ImportError:
        check("pillow", False, "missing", "pip install Pillow")

    return checks


def transcribe_binary():
    from . import transcribe

    return transcribe.whisper_binary()


def cmd_doctor(args) -> int:
    checks = _doctor_checks()
    required_ok = all(c["ok"] for c in checks if c.get("required", True))
    if args.json:
        print(
            json.dumps(
                {"checks": checks, "ready": required_ok},
                indent=2,
            )
        )
    else:
        for check in checks:
            mark = "ok  " if check["ok"] else ("MISS" if check.get("required", True) else "opt ")
            print(f"{mark} {check['name']}: {check['detail']}")
            if not check["ok"] and check["fix"]:
                print(f"       fix: {check['fix']}")
    return 0 if required_ok else 1


def cmd_setup(args) -> int:
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts", "setup.sh")
    if not os.path.exists(script):
        print(f"setup script not found: {script}", file=sys.stderr)
        return 2
    cmd = ["bash", script]
    if args.skip_model:
        cmd += ["--skip-model"]
    return subprocess.call(cmd)


def _backend_for(args) -> object:
    from . import llm

    return llm.get_backend(args.backend)


def cmd_clip(args) -> int:
    result = pipeline.clip_stream(
        args.url,
        out_dir=args.out,
        clips=args.clips,
        backend=_backend_for(args),
        cookies=args.cookies,
        model=args.model,
        skip_render=args.no_render,
        window_minutes=args.window,
        min_score=args.min_score,
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("clips") or args.no_render else 1


def cmd_auto_clip(args) -> int:
    results = pipeline.auto_clip(
        count=args.count,
        out_dir=args.out,
        backend=_backend_for(args),
        cookies=args.cookies,
        clips=args.clips,
        live_only=args.live_only,
    )
    print(json.dumps(results, indent=2))
    return 0


def cmd_live(args) -> int:
    """Record a live stream for a duration, then clip the good moments."""
    from . import fetch

    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)

    _log(f"recording live stream for {args.duration}s from {args.url}")
    video_path = fetch.record_stream_live(args.url, args.duration, out_dir, args.cookies)
    _log(f"recorded: {video_path}")

    result = pipeline.clip_stream(
        args.url,
        out_dir=out_dir,
        clips=args.clips,
        backend=_backend_for(args),
        cookies=args.cookies,
        skip_render=args.no_render,
        window_minutes=args.window,
        min_score=args.min_score,
        local_video_path=video_path,
        source_label=f"live:{args.duration}s",
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("clips") or args.no_render else 1


def cmd_status(args) -> int:
    out_dir = args.out
    if not os.path.isdir(out_dir):
        print(f"no output directory yet: {out_dir}")
        return 0
    for name in sorted(os.listdir(out_dir)):
        path = os.path.join(out_dir, name)
        clips_file = os.path.join(path, "clips.json")
        if not os.path.isfile(clips_file):
            continue
        with open(clips_file, "r", encoding="utf-8") as handle:
            clips = json.load(handle).get("clips", [])
        print(f"{name}: {len(clips)} clip(s)")
        for clip in clips:
            print(f"  - {os.path.basename(clip.get('file', ''))} {clip.get('duration')}s")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gta6-clipper",
        description="Turn long game reaction streams into ready-to-post vertical clips.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup", help="install dependencies and models")
    setup.add_argument("--skip-model", action="store_true", help="do not download the whisper model")
    setup.set_defaults(func=cmd_setup)

    doctor = sub.add_parser("doctor", help="report what is missing and how to fix it")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    clip = sub.add_parser("clip", help="clip one stream")
    clip.add_argument("url")
    clip.add_argument("--out", default=config.DEFAULT_OUT_DIR)
    clip.add_argument("--clips", type=int, default=config.DEFAULT_CLIP_COUNT)
    clip.add_argument("--backend", default="auto", help="LLM backend: opencode, claude, openai, cmd:'<template>', auto")
    clip.add_argument("--model", default=None, help="model name for the chosen backend")
    clip.add_argument("--cookies", default=None, help="browser for --cookies-from-browser, e.g. chrome")
    clip.add_argument("--window", type=int, default=config.WINDOW_MINUTES)
    clip.add_argument("--min-score", type=int, default=config.MIN_SCORE)
    clip.add_argument("--no-render", action="store_true", help="stop after scoring")
    clip.set_defaults(func=cmd_clip)

    auto = sub.add_parser("auto-clip", help="clip today's biggest streams")
    auto.add_argument("--count", type=int, default=7)
    auto.add_argument("--clips", type=int, default=config.DEFAULT_CLIP_COUNT)
    auto.add_argument("--out", default=config.DEFAULT_OUT_DIR)
    auto.add_argument("--backend", default="auto", help="LLM backend: opencode, claude, openai, cmd:'<template>', auto")
    auto.add_argument("--cookies", default=None)
    auto.add_argument("--live-only", action="store_true", help="only clip streams that are live now")
    auto.set_defaults(func=cmd_auto_clip)

    live = sub.add_parser("live", help="record a live stream for a duration, then clip it")
    live.add_argument("url")
    live.add_argument("--duration", type=int, default=3600, help="seconds to record (default 3600 = 1 hour)")
    live.add_argument("--out", default=config.DEFAULT_OUT_DIR)
    live.add_argument("--clips", type=int, default=config.DEFAULT_CLIP_COUNT)
    live.add_argument("--backend", default="auto", help="LLM backend: opencode, claude, openai, cmd:'<template>', auto")
    live.add_argument("--cookies", default=None, help="browser for --cookies-from-browser, e.g. chrome")
    live.add_argument("--window", type=int, default=config.WINDOW_MINUTES)
    live.add_argument("--min-score", type=int, default=config.MIN_SCORE)
    live.add_argument("--no-render", action="store_true", help="stop after scoring")
    live.set_defaults(func=cmd_live)

    status = sub.add_parser("status", help="show what has been clipped")
    status.add_argument("--out", default=config.DEFAULT_OUT_DIR)
    status.set_defaults(func=cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
