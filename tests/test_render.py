"""Tests for caption generation, ffmpeg filtergraph building and facecam geometry."""
import pytest

from gta6clipper.captions import hook_ass, words_to_ass
from gta6clipper.facecam import facecam_box, inset_from_face, is_cornered, stable_box
from gta6clipper.ffmpeg import loudnorm_filter, vertical_filtergraph


class TestCaptions:
    words = [
        {"word": "He", "start": 1.0, "end": 1.4},
        {"word": "cannot", "start": 1.4, "end": 1.9},
        {"word": "believe", "start": 1.9, "end": 2.4},
        {"word": "this", "start": 2.4, "end": 2.8},
    ]

    def test_ass_has_header_and_dialogue(self):
        ass = words_to_ass(self.words)
        assert ass.startswith("[Script Info]")
        assert "Dialogue:" in ass

    def test_every_word_appears(self):
        ass = words_to_ass(self.words)
        for w in ("He", "cannot", "believe", "this"):
            assert w in ass

    def test_karaoke_tags_present_for_word_by_word_highlight(self):
        ass = words_to_ass(self.words)
        assert "\\k" in ass

    def test_clip_start_is_relative_to_clip(self):
        shifted = [
            {"word": "Later", "start": 100.0, "end": 100.5},
            {"word": "words", "start": 100.5, "end": 101.0},
        ]
        ass = words_to_ass(shifted, clip_start=100.0)
        assert "0:00:00.00" in ass

    def test_words_outside_clip_are_dropped(self):
        ass = words_to_ass(self.words, clip_start=0.0, clip_end=1.2)
        assert "believe" not in ass

    def test_empty_words_gives_header_only(self):
        ass = words_to_ass([])
        assert "Dialogue:" not in ass

    def test_hook_ass_has_text_and_style(self):
        ass = hook_ass("HE LOST IT")
        assert "HE LOST IT" in ass
        assert "Dialogue:" in ass


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
