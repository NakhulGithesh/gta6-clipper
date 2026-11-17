"""The pipeline: one stream in, ready-to-post clips out."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time

from . import config, fetch, find_streams, llm, moments, rubric, transcribe
from .loudness import decode_pcm, envelope_from_pcm, find_peaks
from .render import render_clip


def _log(message: str) -> None:
    print(f"[gta6-clipper] {message}", flush=True)


def transcribe_stream(
    audio_path: str, url: str, workdir: str, cookies: str | None = None, prefer_whisper: bool = True
) -> tuple[list[dict], str]:
    """Words with timings. Local whisper.cpp first, YouTube captions as the fallback."""
    if prefer_whisper:
        try:
            words = transcribe.transcribe_whisper(audio_path, workdir)
            if words:
                return words, "whisper.cpp"
        except Exception as exc:
            _log(f"whisper.cpp unavailable ({exc}); falling back to YouTube captions")
    words = transcribe.fetch_captions(url, workdir, cookies)
    if words:
        return words, "youtube-captions"
    raise RuntimeError("no transcript: install whisper.cpp or make sure captions are available")


def score_windows(
    windows: list[moments.Window], backend: llm.Backend, min_score: int = config.MIN_SCORE
) -> tuple[list[dict], list[str]]:
    """Ask the model for clips in every window. Bad answers never become clips."""
    kept: list[dict] = []
    errors: list[str] = []
    for window in windows:
        if not window.text.strip():
            continue
        prompt = rubric.build_scoring_prompt(window.text, window.start, window.end)
        try:
            raw = backend.complete(prompt)
        except Exception as exc:
            errors.append(f"window {window.start:.0f}s: {exc}")
            continue
        found, problems = llm.parse_moments(raw)
        errors.extend(f"window {window.start:.0f}s: {p}" for p in problems)
        for moment in found:
            if float(moment["score"]) < min_score:
                continue
            moment["window_start"] = window.start
            kept.append(moment)
    return kept, errors


def clip_stream(
    url: str,
    out_dir: str = config.DEFAULT_OUT_DIR,
    clips: int = config.DEFAULT_CLIP_COUNT,
    backend: llm.Backend | None = None,
    backend_spec: str = "auto",
    cookies: str | None = None,
    model: str | None = None,
    skip_render: bool = False,
    keep_work: bool = True,
    window_minutes: int = config.WINDOW_MINUTES,
    min_score: int = config.MIN_SCORE,
    query: str = "",
    local_audio_path: str | None = None,
    local_video_path: str | None = None,
    source_label: str | None = None,
) -> dict:
    started = time.time()
    os.makedirs(out_dir, exist_ok=True)

    _log(f"reading metadata for {url}")
    try:
        meta = fetch.fetch_metadata(url, cookies)
    except Exception:
        meta = {
            "id": "",
            "title": source_label or url,
            "channel": "",
            "channel_url": "",
            "duration": 0.0,
            "is_live": True,
            "live_status": "is_live",
            "view_count": 0,
            "webpage_url": url,
            "thumbnail": "",
            "upload_date": "",
        }
    workdir = config.work_dir(out_dir, meta["title"] or meta["id"] or "stream")
    _log(f"stream: {meta['title']} ({meta['duration'] / 60:.0f} min) -> {workdir}")

    if local_audio_path:
        _log(f"using local audio: {local_audio_path}")
        audio_path = local_audio_path
    elif local_video_path:
        _log(f"using local video: {local_video_path}")
        audio_path = local_video_path
    else:
        _log("downloading audio only")
        audio_path = fetch.fetch_audio(url, workdir, cookies)

    _log("transcribing")
    words, source = transcribe_stream(audio_path, url, workdir, cookies)
    _log(f"{len(words)} words via {source}")

    _log("analysing loudness")
    envelope = envelope_from_pcm(decode_pcm(audio_path))
    audio_peaks = find_peaks(envelope, threshold_z=1.5, min_gap_s=5.0, top_n=60)
    _log(f"{len(audio_peaks)} loud moments")

    chat_peaks = []
    try:
        from . import chat

        counts = chat.chat_counts(url, meta["id"])
        chat_peaks = chat.chat_peaks(counts)
        if chat_peaks:
            _log(f"{len(chat_peaks)} chat spikes")
    except Exception:
        pass

    candidates = moments.merge_sources(
        [moments.Candidate(p.start, p.end, "audio", p.score) for p in audio_peaks], chat_peaks
    )
    candidates = moments.dedupe(candidates, min_gap_s=10.0)

    windows = moments.windows_from_words(words, window_minutes=window_minutes)
    _log(f"scoring {len(windows)} transcript windows with the {backend_spec} backend")
    backend = backend or llm.get_backend(backend_spec, model)
    selected, errors = score_windows(windows, backend, min_score=min_score)
    selected = sorted(selected, key=lambda m: -float(m["score"]))[:clips]
    selected.sort(key=lambda m: float(m["start"]))

    with open(os.path.join(workdir, "meta.json"), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2)
    with open(os.path.join(workdir, "transcript.json"), "w", encoding="utf-8") as handle:
        json.dump(words, handle)
    with open(os.path.join(workdir, "moments.json"), "w", encoding="utf-8") as handle:
        json.dump(
            {
                "candidates": [vars(c) for c in candidates],
                "selected": selected,
                "rejected": errors,
            },
            handle,
            indent=2,
        )

    if not selected:
        _log("no clip scored high enough")
        return {
            "meta": meta,
            "workdir": workdir,
            "clips": [],
            "errors": errors,
            "seconds": round(time.time() - started, 1),
        }

    rendered: list[dict] = []
    if not skip_render:
        for index, moment in enumerate(selected, start=1):
            start, end = float(moment["start"]), float(moment["end"])
            _log(f"clip {index}/{len(selected)}: {start:.0f}s-{end:.0f}s {moment['hook']!r}")
            segment_dir = os.path.join(workdir, f"segment-{index:02d}")
            if local_video_path:
                segment = local_video_path
            else:
                segment = fetch.fetch_video_section(url, start, end, segment_dir, cookies)
            out_path = os.path.join(workdir, f"clip-{index:02d}.mp4")
            result = render_clip(
                segment,
                moment,
                words,
                out_path,
                segment_dir,
                facecam_model=config.FACECAM_MODEL if os.path.exists(config.FACECAM_MODEL) else None,
            )
            result["moment"] = moment
            rendered.append(result)
            if not keep_work:
                shutil.rmtree(segment_dir, ignore_errors=True)

    with open(os.path.join(workdir, "clips.json"), "w", encoding="utf-8") as handle:
        json.dump({"clips": rendered}, handle, indent=2)

    return {
        "meta": meta,
        "workdir": workdir,
        "clips": rendered,
        "errors": errors,
        "seconds": round(time.time() - started, 1),
    }


def auto_clip(
    count: int = 7,
    out_dir: str = config.DEFAULT_OUT_DIR,
    backend: llm.Backend | None = None,
    backend_spec: str = "auto",
    cookies: str | None = None,
    live_only: bool = False,
    **kwargs,
) -> list[dict]:
    """Clip the biggest streams of the day."""
    _log(f"looking for today's biggest {find_streams.GAME} streams")
    streams = find_streams.top_streams(count=count, cookies=cookies, live_only=live_only)
    if not streams:
        _log("no streams found")
        return []
    results = []
    for stream in streams:
        url = stream.get("url") or f"https://www.youtube.com/watch?v={stream.get('id')}"
        _log(f"stream: {stream.get('title')} by {stream.get('channel')}")
        try:
            results.append(
                clip_stream(
                    url,
                    out_dir=out_dir,
                    backend=backend,
                    backend_spec=backend_spec,
                    cookies=cookies,
                    **kwargs,
                )
            )
        except Exception as exc:
            _log(f"failed: {exc}")
            results.append({"meta": stream, "clips": [], "errors": [str(exc)]})
    return results
