"""Tests for caption generation, ffmpeg filtergraph building and facecam geometry."""
import os

import pytest

from gta6clipper import captions
from gta6clipper.facecam import facecam_box, inset_from_face, is_cornered, stable_box
from gta6clipper.ffmpeg import loudnorm_filter, vertical_filtergraph


class TestCaptions:
    words = [
        {"word": "He", "start": 1.0, "end": 1.4},
        {"word": "cannot", "start": 1.4, "end": 1.9},
        {"word": "believe", "start": 1.9, "end": 2.4},
        {"word": "this", "start": 2.4, "end": 2.8},
    ]

    def test_events_group_words_into_phrases(self):
        events = captions.build_events(self.words)
        assert events
        assert [w["text"] for w in events[0]["words"]] == ["He", "cannot", "believe"]

    def test_event_times_are_relative_to_the_clip(self):
        shifted = [
            {"word": "Later", "start": 100.0, "end": 100.5},
            {"word": "words", "start": 100.5, "end": 101.0},
        ]
        events = captions.build_events(shifted, clip_start=100.0)
        assert events[0]["start"] == pytest.approx(0.0)

    def test_words_outside_the_clip_are_dropped(self):
        events = captions.build_events(self.words, clip_start=0.0, clip_end=1.2)
        texts = [w["text"] for event in events for w in event["words"]]
        assert "believe" not in texts

    def test_state_points_at_the_active_word(self):
        events = captions.build_events(self.words)
        index, word_index = captions.state_at(events, 1.5)
        assert index == 0
        assert events[0]["words"][word_index]["text"] == "cannot"

    def test_state_is_none_outside_any_event(self):
        events = captions.build_events(self.words)
        assert captions.state_at(events, 99.0) is None

    def test_caption_layer_renders_a_transparent_video(self, tmp_path):
        events = captions.build_events(self.words)
        out = str(tmp_path / "captions.mov")
        captions.render_caption_layer(events, out, duration=3.0)
        assert os.path.getsize(out) > 1000

    def test_hook_layer_renders_a_transparent_video(self, tmp_path):
        out = str(tmp_path / "hook.mov")
        captions.render_hook_layer("HE LOST IT", out, duration=3.0)
        assert os.path.getsize(out) > 1000

    def test_wrapped_hook_lines_fit_the_available_width(self):
        from PIL import Image, ImageDraw

        draw = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        font = captions._load_font(76)
        available = 1080 - 140
        lines = captions._wrap(
            "THIS CHANGES EVERYTHING AND EVERYONE WILL KNOW ABOUT IT", font, draw, available
        )
        assert len(lines) >= 2
        for line in lines:
            assert draw.textlength(line, font=font) <= available

    def test_hook_shrinks_until_it_fits(self):
        lines, font = captions._fit_hook(
            "THIS CHANGES EVERYTHING AND EVERYONE WILL KNOW ABOUT IT SOON", 1080, 76, None
        )
        assert len(lines) <= 2


class TestFiltergraph:
    def test_no_facecam_centres_gameplay(self):
        fg = vertical_filtergraph(1920, 1080, None)
        assert "scale=1080:1920" in fg
        assert "overlay=(W-w)/2:(H-h)/2" in fg

    def test_facecam_is_cropped_and_overlaid_at_top(self):
        fg = vertical_filtergraph(1920, 1080, (0, 0, 480, 270))
        assert "crop=480:270:0:0" in fg
        assert "overlay=(W-w)/2:40" in fg

    def test_output_size_is_set(self):
        fg = vertical_filtergraph(1920, 1080, None)
        assert "scale=1080:1920" in fg
        assert "crop=1080:1920" in fg

    def test_loudnorm_targets_minus_14_lufs(self):
        assert "I=-14" in loudnorm_filter()

    def test_layers_are_overlaid_at_their_position(self):
        from gta6clipper.ffmpeg import render_command

        cmd = render_command(
            "in.mp4", "out.mp4", vertical_filtergraph(1920, 1080, None),
            layers=[("hook.mov", 0, 420), ("captions.mov", 0, 1500)],
        )
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "overlay=0:420" in graph
        assert "overlay=0:1500" in graph
        assert cmd.count("-i") == 3


class TestFacecamGeometry:
    def test_corner_face_is_cornered(self):
        assert is_cornered((20, 20, 200, 150), 1920, 1080)

    def test_centred_large_face_is_not_an_inset(self):
        assert not is_cornered((700, 100, 500, 500), 1920, 1080)

    def test_face_too_big_is_not_an_inset(self):
        assert not is_cornered((10, 10, 900, 900), 1920, 1080)

    def test_inset_from_face_grows_to_16_9_box(self):
        x, y, w, h = inset_from_face((100, 100, 120, 140), 1920, 1080)
        assert w / h == pytest.approx(16 / 9, rel=0.2)
        assert w > 120

    def test_stable_box_returns_median(self):
        boxes = [(100, 100, 200, 120), (104, 98, 200, 120), (98, 102, 200, 120)]
        assert stable_box(boxes, 1920, 1080) is not None

    def test_stable_box_rejects_moving_subject(self):
        boxes = [(100, 100, 200, 120), (900, 600, 200, 120), (400, 300, 200, 120)]
        assert stable_box(boxes, 1920, 1080) is None

    def test_facecam_box_handles_missing_model(self, tmp_path):
        assert facecam_box("missing.mp4", tmp_path / "nope.onnx") is None
