"""Tests for loudness envelope, peak detection and candidate windowing."""
import math
import struct

import pytest

from gta6clipper.loudness import envelope_from_pcm, find_peaks, rms
from gta6clipper.moments import Candidate, dedupe, merge_sources, windows_from_words


def pcm(amplitude: float, n: int, rate: int = 16000) -> bytes:
    sample = int(32767 * amplitude)
    return struct.pack("<%dh" % n, *([sample] * n))


class TestEnvelope:
    def test_rms_of_silence_is_zero(self):
        assert rms(pcm(0.0, 1000)) == pytest.approx(0.0)

    def test_rms_scales_with_amplitude(self):
        quiet = rms(pcm(0.1, 8000))
        loud = rms(pcm(0.8, 8000))
        assert loud > quiet * 5

    def test_envelope_has_one_value_per_window(self):
        data = pcm(0.5, 16000)  # 1 second at 16 kHz
        env = envelope_from_pcm(data, 16000, window_seconds=0.5)
        assert len(env) == 2
        assert all(v > 0 for v in env)

    def test_envelope_handles_partial_final_window(self):
        data = pcm(0.5, 8000)  # half a second
        env = envelope_from_pcm(data, 16000, window_seconds=0.5)
        assert len(env) == 1


class TestPeaks:
    def test_finds_loud_burst_in_quiet_track(self):
        rate = 16000
        quiet = pcm(0.02, rate * 10)
        burst = pcm(0.9, rate * 2)
        silence = pcm(0.02, rate * 10)
        env = envelope_from_pcm(quiet + burst + silence, rate, 0.5)
        peaks = find_peaks(env, threshold_z=1.5, min_gap_s=2.0, top_n=10)
        assert peaks, "expected at least one peak"
        peak = peaks[0]
        assert 9.0 <= peak.start <= 11.0
        assert peak.end > peak.start

    def test_uniform_noise_has_no_peaks(self):
        import random

        random.seed(7)
        rate = 16000
        data = struct.pack("<%dh" % (rate * 8), *[random.randint(-300, 300)] * (rate * 8))
        env = envelope_from_pcm(data, rate, 0.5)
        assert find_peaks(env, threshold_z=3.0, min_gap_s=2.0, top_n=10) == []

    def test_peaks_are_capped_by_top_n(self):
        rate = 16000
        data = b""
        for _ in range(12):
            data += pcm(0.02, rate) + pcm(0.9, rate)
        env = envelope_from_pcm(data, rate, 0.5)
        peaks = find_peaks(env, threshold_z=1.0, min_gap_s=0.5, top_n=3)
        assert len(peaks) <= 3

    def test_min_gap_suppresses_neighbours(self):
        rate = 16000
        data = pcm(0.9, rate * 6)
        env = envelope_from_pcm(data, rate, 0.5)
        peaks = find_peaks(env, threshold_z=0.0, min_gap_s=5.0, top_n=10)
        assert len(peaks) == 1


class TestWindows:
    def test_splits_transcript_into_twelve_minute_windows(self):
        # one word every 10 seconds for 30 minutes
        words = [{"word": "hi", "start": i * 10.0, "end": i * 10.0 + 1} for i in range(180)]
        wins = windows_from_words(words, window_minutes=12)
        assert len(wins) == 3
        assert wins[0].start == 0.0
        assert wins[1].start == pytest.approx(12 * 60)
        assert wins[-1].end >= 29 * 60

    def test_short_transcript_is_one_window(self):
        words = [{"word": "hi", "start": 1.0, "end": 2.0}]
        assert len(windows_from_words(words, window_minutes=12)) == 1

    def test_empty_transcript_yields_no_windows(self):
        assert windows_from_words([], window_minutes=12) == []


class TestMerge:
    def test_overlapping_audio_and_chat_peak_becomes_one_candidate(self):
        audio = [Candidate(start=10.0, end=30.0, source="audio", score=0.8)]
        chat = [Candidate(start=20.0, end=40.0, source="chat", score=0.6)]
        merged = merge_sources(audio, chat, overlap_s=5.0)
        assert len(merged) == 1
        assert merged[0].source == "both"
        assert merged[0].start == 10.0
        assert merged[0].end == 40.0

    def test_distant_peaks_stay_separate(self):
        audio = [Candidate(start=10.0, end=20.0, source="audio", score=0.8)]
        chat = [Candidate(start=100.0, end=120.0, source="chat", score=0.6)]
        assert len(merge_sources(audio, chat, overlap_s=5.0)) == 2

    def test_dedupe_keeps_highest_scoring_overlap(self):
        a = Candidate(start=0.0, end=30.0, source="audio", score=0.9)
        b = Candidate(start=5.0, end=35.0, source="chat", score=0.4)
        out = dedupe([a, b], min_gap_s=10.0)
        assert len(out) == 1
        assert out[0].score == 0.9
