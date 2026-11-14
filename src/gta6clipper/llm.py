"""LLM backends for moment picking.

Two routes, same interface:
- claude: the Claude Code CLI on a subscription. No API key, best picks.
- ollama: a local model. Free, slower, rougher picks.

Neither route sends audio anywhere. The transcript goes to the model, the audio
stays on the machine.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

from .rubric import validate_moment

DEFAULT_OLLAMA_MODEL = "qwen3.5:27b"


class Backend:
    name = "backend"

    def command(self, prompt: str) -> list[str]:
        raise NotImplementedError

    def complete(self, prompt: str, timeout: int = 900) -> str:
        proc = subprocess.run(
            self.command(prompt), capture_output=True, text=True, timeout=timeout
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"{self.name} backend failed: {(proc.stderr or proc.stdout).strip()[:500]}"
            )
        return proc.stdout.strip()


class ClaudeCliBackend(Backend):
    name = "claude"

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("GTA6_CLIPPER_CLAUDE_MODEL") or None

    def command(self, prompt: str) -> list[str]:
        cmd = [shutil.which("claude") or "claude", "-p", prompt, "--output-format", "text"]
        if self.model:
            cmd += ["--model", self.model]
        return cmd


class OllamaBackend(Backend):
    name = "ollama"

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("GTA6_CLIPPER_OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL

    def command(self, prompt: str) -> list[str]:
        return [shutil.which("ollama") or "ollama", "run", self.model, prompt]


def get_backend(mode: str = "claude", model: str | None = None) -> Backend:
    mode = (mode or "claude").lower()
    if mode == "claude":
        return ClaudeCliBackend(model)
    if mode == "ollama":
        return OllamaBackend(model)
    raise ValueError(f"unknown mode: {mode} (use claude or ollama)")


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _extract_json_array(raw: str) -> list | None:
    if not raw:
        return None
    text = raw.strip()
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("["), text.rfind("]")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    if isinstance(parsed, dict):
        parsed = parsed.get("moments", [])
    if not isinstance(parsed, list):
        return None
    return parsed


def parse_moments(raw: str) -> tuple[list[dict], list[str]]:
    """Model output -> (usable moments, reasons the rest were dropped).

    A malformed answer never becomes a clip. The raw text is kept by the caller
    so a bad model can be inspected instead of guessed at.
    """
    items = _extract_json_array(raw)
    if items is None:
        return [], ["could not parse a JSON array from the model response"]

    good: list[dict] = []
    errors: list[str] = []
    for item in items:
        moment_errors = validate_moment(item)
        if moment_errors:
            errors.append(f"{item.get('hook', item)!r}: " + "; ".join(moment_errors))
        else:
            good.append(item)
    return good, errors
