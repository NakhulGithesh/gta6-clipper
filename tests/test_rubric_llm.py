"""Tests for the scoring rubric and LLM response handling."""
import shutil

import pytest

from gta6clipper.llm import (
    ClaudeCliBackend,
    CommandBackend,
    OpenAIBackend,
    OpenCodeBackend,
    get_backend,
    parse_moments,
)
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

    def test_prompt_asks_for_postable_duration(self):
        p = build_scoring_prompt("[00:01] hello", 0.0, 720.0)
        assert "15" in p and "45" in p
        assert "seconds" in p


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
    def test_get_backend_by_spec(self, monkeypatch):
        # claude binary is installed
        if shutil.which("claude"):
            assert isinstance(get_backend("claude"), ClaudeCliBackend)
        # openai probe may or may not reach a server; mock it
        monkeypatch.setattr(OpenAIBackend, "probe", lambda self: True)
        assert isinstance(get_backend("openai"), OpenAIBackend)

    def test_explicit_backend_raises_when_unreachable(self, monkeypatch):
        import gta6clipper.llm as llm_mod

        monkeypatch.setattr(llm_mod, "_opencode_path", lambda: None)
        with pytest.raises(RuntimeError):
            get_backend("opencode")

    def test_cmd_backend(self):
        b = CommandBackend("printf '%s' hi")
        assert isinstance(b, CommandBackend)
        assert b.complete("ignored") == "hi"

    def test_cmd_backend_passes_prompt_through(self):
        b = CommandBackend("printf '%s' {prompt}")
        assert b.complete("hello") == "hello"

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError):
            get_backend("gpt")

    def test_auto_raises_when_nothing_reachable(self, monkeypatch):
        import gta6clipper.llm as llm_mod

        monkeypatch.setattr(llm_mod.OpenCodeBackend, "probe", lambda self: False)
        monkeypatch.setattr(llm_mod.ClaudeCliBackend, "probe", lambda self: False)
        monkeypatch.setattr(llm_mod.OpenAIBackend, "probe", lambda self: False)
        with pytest.raises(RuntimeError):
            get_backend("auto")

    def test_claude_backend_probe(self):
        b = ClaudeCliBackend()
        # probe only checks the binary exists; may be False if claude isn't installed
        assert b.probe() == (shutil.which("claude") is not None)

    def test_openai_backend_uses_base_and_model(self):
        b = OpenAIBackend(base_url="http://x/v1", model="qwen3.8-27b")
        assert b.base_url == "http://x/v1"
        assert b.model == "qwen3.8-27b"


class TestOpenCodePath:
    def test_env_override_wins(self, monkeypatch, tmp_path):
        import gta6clipper.llm as llm_mod

        fake = tmp_path / "opencode"
        fake.write_text("#!/bin/sh\n")
        fake.chmod(0o755)
        monkeypatch.setenv("OPENCODE_CLI", str(fake))
        assert llm_mod._opencode_path() == str(fake)

    def test_app_bundle_is_used_when_not_on_path(self, monkeypatch, tmp_path):
        import gta6clipper.llm as llm_mod

        monkeypatch.delenv("OPENCODE_CLI", raising=False)
        monkeypatch.setattr(llm_mod.shutil, "which", lambda name: None)
        fake = tmp_path / "opencode-cli"
        fake.write_text("")
        monkeypatch.setattr(llm_mod, "_OPENCODE_FALLBACKS", (str(fake),))
        assert llm_mod._opencode_path() == str(fake)

    def test_missing_everywhere_returns_none(self, monkeypatch):
        import gta6clipper.llm as llm_mod

        monkeypatch.delenv("OPENCODE_CLI", raising=False)
        monkeypatch.setattr(llm_mod.shutil, "which", lambda name: None)
        monkeypatch.setattr(llm_mod, "_OPENCODE_FALLBACKS", ("/nope/opencode",))
        assert llm_mod._opencode_path() is None


class TestAutoFallback:
    def _stub(self, monkeypatch, name, *, text=None, error=None, reachable=True):
        import gta6clipper.llm as llm_mod

        class Stub(llm_mod.Backend):
            pass

        stub = Stub()
        stub.name = name
        stub.probe = lambda: reachable
        if error is not None:
            def complete(prompt, timeout=900):
                raise RuntimeError(error)
        else:
            def complete(prompt, timeout=900):
                return text
        stub.complete = complete
        return stub

    def test_returns_first_route_that_answers(self, monkeypatch):
        import gta6clipper.llm as llm_mod

        good = self._stub(monkeypatch, "good", text="OK")
        backend = llm_mod.AutoBackend([good])
        assert backend.complete("prompt") == "OK"
        assert backend.name == "good"

    def test_skips_a_route_that_raises(self, monkeypatch):
        import gta6clipper.llm as llm_mod

        broken = self._stub(monkeypatch, "claude", error="not logged in")
        good = self._stub(monkeypatch, "opencode", text="OK")
        backend = llm_mod.AutoBackend([broken, good])
        assert backend.complete("prompt") == "OK"
        assert backend.name == "opencode"

    def test_remembers_the_working_route(self, monkeypatch):
        import gta6clipper.llm as llm_mod

        broken = self._stub(monkeypatch, "claude", error="not logged in")
        good = self._stub(monkeypatch, "opencode", text="OK")
        backend = llm_mod.AutoBackend([broken, good])
        backend.complete("first")
        assert backend._chosen is good
        assert backend.complete("second") == "OK"

    def test_reports_every_failure(self, monkeypatch):
        import gta6clipper.llm as llm_mod

        a = self._stub(monkeypatch, "a", error="boom a")
        b = self._stub(monkeypatch, "b", error="boom b")
        backend = llm_mod.AutoBackend([a, b])
        with pytest.raises(RuntimeError) as excinfo:
            backend.complete("prompt")
        message = str(excinfo.value)
        assert "boom a" in message and "boom b" in message

    def test_unreachable_routes_are_skipped(self, monkeypatch):
        import gta6clipper.llm as llm_mod

        missing = self._stub(monkeypatch, "missing", text="should not run", reachable=False)
        good = self._stub(monkeypatch, "good", text="OK")
        assert llm_mod.AutoBackend([missing, good]).complete("p") == "OK"

    def test_get_backend_auto_is_fallthrough(self, monkeypatch):
        import gta6clipper.llm as llm_mod

        monkeypatch.setattr(llm_mod.OpenCodeBackend, "probe", lambda self: True)
        assert isinstance(get_backend("auto"), llm_mod.AutoBackend)
