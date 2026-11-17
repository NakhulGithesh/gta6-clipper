"""Live stream recording verification.

Run: python3 scripts/verify_live.py

Verifies:
- record_stream_live_command builds a valid ffmpeg command with duration
- record_stream_live resolves stream URL via yt-dlp with cookies, records via ffmpeg
- clip_stream accepts local_video_path and skips download
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from gta6clipper import fetch, pipeline  # noqa: E402


def test_command_contains_duration() -> None:
    cmd = fetch.record_stream_live_command("https://stream.example.com/live", 3600, "/tmp/out")
    assert cmd[0] == "ffmpeg"
    assert "-t" in cmd
    assert "3600" in cmd
    assert "-c" in cmd
    assert "copy" in cmd
    assert "-vn" not in cmd  # video is included


def test_record_stream_live_with_mock(monkeypatch_obj) -> None:  # type: ignore[no-untyped-def]
    calls = []
    outdir = tempfile.mkdtemp()

    def fake_run(cmd, timeout=7200):
        calls.append(list(cmd))
        if cmd and cmd[0] == "ffmpeg":
            out_path = os.path.join(outdir, "live_stream.mp4")
            with open(out_path, "wb") as f:
                f.write(b"fake mp4 data")
        class Result:
            returncode = 0
            stdout = "https://direct.example.com/stream.m3u8\n"
            stderr = ""
        return Result()

    monkeypatch_obj.setattr(fetch, "run", fake_run)
    path = fetch.record_stream_live("https://x/y", 300, outdir, cookies="chrome")
    assert path == os.path.join(outdir, "live_stream.mp4")
    assert os.path.exists(path)
    assert any("--cookies-from-browser" in c and "chrome" in c for c in calls)
    ffmpeg_calls = [c for c in calls if c[0] == "ffmpeg"]
    assert len(ffmpeg_calls) == 1
    assert any("direct.example.com" in arg for arg in ffmpeg_calls[0])


def test_record_audio_live_alias() -> None:
    """record_audio_live is an alias for record_stream_live."""
    assert fetch.record_audio_live is fetch.record_stream_live
    assert fetch.record_audio_live_command is fetch.record_stream_live_command


def test_clip_stream_accepts_local_video(monkeypatch_obj) -> None:  # type: ignore[no-untyped-def]
    """clip_stream with local_video_path must not call fetch_audio or fetch_video_section."""
    download_calls = []

    def fake_fetch_audio(url, outdir, cookies=None):
        download_calls.append(url)
        raise AssertionError("fetch_audio should not be called with local_video_path")

    import gta6clipper.fetch as fetch_mod  # noqa: PLC0415
    monkeypatch_obj.setattr(fetch_mod, "fetch_audio", fake_fetch_audio)

    import gta6clipper.pipeline as pipeline_mod  # noqa: PLC0415

    # Mock transcribe to return words quickly
    def fake_transcribe_stream(audio_path, url, workdir, cookies=None, prefer_whisper=True):
        return [
            {"word": "test", "start": 0.0, "end": 1.0},
            {"word": "words", "start": 1.0, "end": 2.0},
        ], "mock"

    monkeypatch_obj.setattr(pipeline_mod, "transcribe_stream", fake_transcribe_stream)

    # Mock the backend to return one valid moment
    from gta6clipper import llm  # noqa: PLC0415

    class StubBackend(llm.Backend):
        name = "stub"
        def command(self, prompt): return ["stub"]
        def complete(self, prompt, timeout=900):
            import json as _json
            return _json.dumps([{
                "start": 0.0, "end": 25.0, "type": "hot_take", "score": 80,
                "hook": "Test moment", "title": "T", "caption": "C",
                "hashtags": ["#GTA6", "#Shorts", "#Gaming"],
                "needs_context": False, "starts_with_filler": False
            }])

    monkeypatch_obj.setattr(pipeline_mod.llm, "get_backend", lambda *a, **k: StubBackend())

    # Mock render_clip to avoid actual ffmpeg
    def fake_render_clip(video_path, clip, words, out_path, workdir,
                         facecam_model=None, duration=None):
        return {"file": out_path, "post_caption": "caption", "facecam": None,
                "duration": 25.0, "start": 0.0, "end": 25.0}

    monkeypatch_obj.setattr(pipeline_mod, "render_clip", fake_render_clip)

    # Mock loudness decode to avoid ffmpeg on the fake audio
    monkeypatch_obj.setattr(pipeline_mod, "decode_pcm", lambda path: b"\x00\x00" * 1000)

    result = pipeline_mod.clip_stream(
        "https://x/y",
        out_dir=tempfile.mkdtemp(),
        clips=1,
        backend=StubBackend(),
        local_video_path="/tmp/fake_video.mp4",
        source_label="live",
    )
    assert len(download_calls) == 0, f"fetch_audio was called: {download_calls}"
    assert len(result["clips"]) == 1
    assert result["clips"][0]["file"].endswith("clip-01.mp4")


def main() -> int:
    class SimpleMonkeypatch:
        def __init__(self):
            self._patches = []

        def setattr(self, obj, name, value):
            orig = getattr(obj, name)
            setattr(obj, name, value)
            self._patches.append((obj, name, orig))

        def undo(self):
            for obj, name, orig in self._patches:
                setattr(obj, name, orig)

    failures = []

    mp = SimpleMonkeypatch()
    try:
        test_command_contains_duration()
    except Exception as exc:
        failures.append(f"test_command_contains_duration: {exc}")

    mp = SimpleMonkeypatch()
    try:
        test_record_stream_live_with_mock(mp)
    except Exception as exc:
        failures.append(f"test_record_stream_live_with_mock: {exc}")
    finally:
        mp.undo()

    mp = SimpleMonkeypatch()
    try:
        test_record_audio_live_alias()
    except Exception as exc:
        failures.append(f"test_record_audio_live_alias: {exc}")

    mp = SimpleMonkeypatch()
    try:
        test_clip_stream_accepts_local_video(mp)
    except Exception as exc:
        failures.append(f"test_clip_stream_accepts_local_video: {exc}")
    finally:
        mp.undo()

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("LIVE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
