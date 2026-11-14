"""Tests for source fetching, transcription parsing and stream discovery."""
import json
import subprocess

import pytest

from gta6clipper import fetch
from gta6clipper.find_streams import rank_streams
from gta6clipper.transcribe import parse_vtt, parse_whisper_json


class TestFetchCommands:
    def test_audio_download_uses_audio_only_format(self):
        cmd = fetch.audio_command("https://x/y", "/tmp/out", cookies=None)
        assert "-f" in cmd and "ba" in cmd
        assert "--extract-audio" in cmd

    def test_cookies_flag_is_passed_through(self):
        cmd = fetch.audio_command("https://x/y", "/tmp/out", cookies="chrome")
        assert "--cookies-from-browser" in cmd
        assert "chrome" in cmd

    def test_video_section_download_uses_download_sections(self):
        cmd = fetch.video_section_command(
            "https://x/y", 120.0, 180.0, "/tmp/out", cookies=None
        )
        assert any(a.startswith("*120.0-180.0") for a in cmd)
        assert "--download-sections" in cmd

    def test_metadata_command_dumps_json(self):
        cmd = fetch.metadata_command("https://x/y", cookies=None)
        assert "--dump-single-json" in cmd
        assert "--no-playlist" in cmd


class TestMetadataParsing:
    def test_live_stream_is_detected(self):
        info = {
            "title": "GTA 6 reaction",
            "channel": "Streamer",
            "duration": 14400,
            "is_live": True,
            "live_status": "is_live",
            "view_count": 5000,
        }
        meta = fetch.parse_metadata(info)
        assert meta["is_live"] is True
        assert meta["duration"] == 14400

    def test_missing_fields_do_not_raise(self):
        meta = fetch.parse_metadata({})
        assert meta["duration"] == 0
        assert meta["is_live"] is False


class TestTranscribeParsing:
    def test_whisper_json_words_are_extracted(self):
        payload = {
            "transcription": [
                {
                    "offsets": {"from": 1000, "to": 2500},
                    "text": " hello world",
                    "tokens": [
                        {"text": " hello", "offsets": {"from": 1000, "to": 1700}},
                        {"text": " world", "offsets": {"from": 1700, "to": 2500}},
                    ],
                }
            ]
        }
        words = parse_whisper_json(payload)
        assert [w["word"] for w in words] == ["hello", "world"]
        assert words[0]["start"] == pytest.approx(1.0)
        assert words[1]["end"] == pytest.approx(2.5)

    def test_vtt_is_parsed_with_timestamps(self):
        vtt = (
            "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHe cannot believe this\n\n"
            "00:00:04.500 --> 00:00:06.000\nNo way\n"
        )
        words = parse_vtt(vtt)
        assert [w["word"] for w in words][:3] == ["He", "cannot", "believe"]
        assert words[0]["start"] == pytest.approx(1.0)

    def test_empty_vtt_gives_no_words(self):
        assert parse_vtt("WEBVTT\n") == []


class TestFindStreams:
    def test_ranks_live_streams_by_viewers(self):
        streams = [
            {"id": "a", "title": "x", "is_live": False, "view_count": 900000},
            {"id": "b", "title": "y", "is_live": True, "view_count": 100},
            {"id": "c", "title": "z", "is_live": True, "view_count": 900},
        ]
        ranked = rank_streams(streams, limit=2, live_only=True)
        assert [s["id"] for s in ranked] == ["c", "b"]

    def test_live_streams_come_before_vods(self):
        streams = [
            {"id": "vod", "title": "x", "is_live": False, "view_count": 900000},
            {"id": "live", "title": "y", "is_live": True, "view_count": 100},
        ]
        ranked = rank_streams(streams, limit=2)
        assert [s["id"] for s in ranked] == ["live", "vod"]

    def test_short_vods_are_skipped(self):
        streams = [
            {"id": "short", "title": "x", "is_live": False, "view_count": 900000, "duration": 30},
            {"id": "long", "title": "y", "is_live": False, "view_count": 10, "duration": 4000},
        ]
        ranked = rank_streams(streams, limit=2, min_duration=600)
        assert [s["id"] for s in ranked] == ["long"]

    def test_filters_non_live_when_required(self):
        streams = [{"id": "a", "title": "x", "is_live": False, "view_count": 5}]
        assert rank_streams(streams, limit=5, live_only=True) == []

    def test_missing_view_count_is_tolerated(self):
        streams = [{"id": "a", "title": "x", "is_live": True}]
        ranked = rank_streams(streams, limit=1)
        assert ranked[0]["id"] == "a"
