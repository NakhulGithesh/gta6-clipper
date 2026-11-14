"""Tests for the scoring rubric and LLM response handling."""
import pytest

from gta6clipper.llm import OllamaBackend, ClaudeCliBackend, get_backend, parse_moments
from gta6clipper.rubric import MOMENT_TYPES, build_scoring_prompt, validate_moment


def good_moment(**overrides):
    m = {
        "start": 120.0,
        "end": 165.0,
        "type": "freakout",
        "score": 82,
        "hook": "He was NOT ready for this",
        "title": "Streamer loses it over GTA 6",
        "caption": "He genuinely did not see that coming.",
        "hashtags": ["#GTA6", "#Shorts", "#Gaming"],
        "needs_context": False,
        "starts_with_filler": False,
    }
    m.update(overrides)
    return m


class TestValidateMoment:
    def test_valid_moment_has_no_errors(self):
        assert validate_moment(good_moment()) == []

    def test_context_dependent_moment_is_rejected(self):
        errs = validate_moment(good_moment(needs_context=True))
        assert any("context" in e for e in errs)

    def test_filler_start_is_rejected(self):
        errs = validate_moment(good_moment(starts_with_filler=True))
        assert any("filler" in e for e in errs)

    def test_unknown_type_is_rejected(self):
        errs = validate_moment(good_moment(type="vibes"))
        assert any("type" in e for e in errs)

    def test_end_before_start_is_rejected(self):
        errs = validate_moment(good_moment(start=100.0, end=50.0))
        assert errs

    def test_score_out_of_range_is_rejected(self):
        assert validate_moment(good_moment(score=120))
        assert validate_moment(good_moment(score=-1))

    def test_too_long_is_rejected(self):
        assert validate_moment(good_moment(end=120.0 + 600.0))

    def test_missing_hook_is_rejected(self):
        assert validate_moment(good_moment(hook=""))

    def test_hashtags_must_be_hashtags(self):
        assert validate_moment(good_moment(hashtags=["GTA6", "Shorts"]))
        assert validate_moment(good_moment(hashtags=[]))

    def test_every_known_type_is_accepted(self):
        for t in MOMENT_TYPES:
            assert validate_moment(good_moment(type=t)) == []


class TestPrompt:
    def test_prompt_states_the_types_and_json_shape(self):
        p = build_scoring_prompt("[00:01] hello", 0.0, 720.0)
        assert "first_reaction" in p
        assert "freakout" in p
        assert "JSON" in p
        assert "needs_context" in p

    def test_prompt_contains_the_transcript_window(self):
        p = build_scoring_prompt("[00:01] the streamer screams", 0.0, 720.0)
        assert "the streamer screams" in p


class TestParseMoments:
    def test_plain_json_array(self):
        import json

        raw = json.dumps([good_moment()])
        moments, errors = parse_moments(raw)
        assert len(moments) == 1
        assert errors == []

    def test_markdown_fenced_json(self):
        raw = "Here you go:\n```json\n" + __import__("json").dumps([good_moment()]) + "\n```\n"
        moments, errors = parse_moments(raw)
        assert len(moments) == 1

    def test_json_with_preamble_and_trailing_text(self):
        import json

        raw = "Sure! " + json.dumps([good_moment()]) + " Let me know."
        moments, errors = parse_moments(raw)
        assert len(moments) == 1

    def test_invalid_moment_is_reported_not_kept(self):
        import json

        raw = json.dumps([good_moment(), good_moment(needs_context=True)])
        moments, errors = parse_moments(raw)
        assert len(moments) == 1
        assert errors

    def test_garbage_returns_error(self):
        moments, errors = parse_moments("not json at all")
        assert moments == []
        assert errors


class TestBackends:
    def test_get_backend_by_mode(self):
        assert isinstance(get_backend("claude"), ClaudeCliBackend)
        assert isinstance(get_backend("ollama"), OllamaBackend)

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError):
            get_backend("gpt")

    def test_claude_backend_builds_command_without_api_key(self):
        b = ClaudeCliBackend()
        cmd = b.command("hello")
        assert cmd[0].endswith("claude")
        assert "-p" in cmd
        assert "hello" in cmd

    def test_ollama_backend_uses_configured_model(self):
        b = OllamaBackend(model="qwen3.5:9b")
        cmd = b.command("hello")
        assert "qwen3.5:9b" in cmd
        assert "hello" in cmd
