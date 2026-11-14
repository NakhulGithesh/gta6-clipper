"""LLM backends for moment picking.

Pluggable routes, same interface: ``complete(prompt) -> str``. Pick one with
``--backend`` or let ``auto`` probe for the first one that answers.

Routes:
- ``opencode``   - the opencode CLI (``opencode run <prompt>``)
- ``claude``     - the Claude Code CLI (``claude -p <prompt>``)
- ``openai``     - any OpenAI-compatible chat-completions endpoint (LM Studio,
                   llama.cpp server, vLLM, Ollama's /v1, a cloud API, etc.)
- ``cmd:<t>``    - any shell command with ``{prompt}`` as a placeholder
- ``auto``       - probes opencode, claude, the openai endpoint, then
                   GTA6_CLIPPER_LLM_COMMAND, using the first one that answers

Only the transcript goes to the model. Audio stays on the machine.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request

from .rubric import validate_moment

DEFAULT_LLM_BASE_URL = os.environ.get("GTA6_CLIPPER_LLM_BASE_URL", "http://localhost:1234/v1")
DEFAULT_LLM_MODEL = os.environ.get("GTA6_CLIPPER_LLM_MODEL", "")


class Backend:
    """A route that turns a prompt into text."""

    name = "backend"

    def probe(self) -> bool:
        """Return True if this route is reachable and answers."""
        raise NotImplementedError

    def complete(self, prompt: str, timeout: int = 900) -> str:
        raise NotImplementedError


class OpenCodeBackend(Backend):
    name = "opencode"

    def probe(self) -> bool:
        return shutil.which("opencode") is not None

    def complete(self, prompt: str, timeout: int = 900) -> str:
        path = shutil.which("opencode") or "opencode"
        proc = subprocess.run(
            [path, "run", prompt], capture_output=True, text=True, timeout=timeout
        )
        if proc.returncode != 0:
            raise RuntimeError(f"opencode failed: {(proc.stderr or proc.stdout).strip()[:500]}")
        return proc.stdout.strip()


class ClaudeCliBackend(Backend):
    name = "claude"

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("GTA6_CLIPPER_CLAUDE_MODEL") or None

    def probe(self) -> bool:
        return shutil.which("claude") is not None

    def complete(self, prompt: str, timeout: int = 900) -> str:
        path = shutil.which("claude") or "claude"
        cmd = [path, "-p", prompt, "--output-format", "text"]
        if self.model:
            cmd += ["--model", self.model]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            message = (proc.stderr or proc.stdout).strip()
            if "Not logged in" in message:
                raise RuntimeError(
                    "the Claude Code CLI is not logged in: run `claude` once and use /login"
                )
            raise RuntimeError(f"claude failed: {message[:500]}")
        return proc.stdout.strip()


class OpenAIBackend(Backend):
    """Any OpenAI-compatible chat-completions endpoint."""

    name = "openai"

    def __init__(self, base_url: str | None = None, model: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or DEFAULT_LLM_BASE_URL).rstrip("/")
        self.model = model or DEFAULT_LLM_MODEL
        self.api_key = api_key or os.environ.get("GTA6_CLIPPER_LLM_API_KEY") or ""

    def probe(self) -> bool:
        try:
            body = json.dumps(
                {
                    "model": self.model or "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "OK"}],
                    "max_tokens": 1,
                    "temperature": 0,
                }
            ).encode()
            req = urllib.request.Request(
                self.base_url + "/chat/completions",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
                },
            )
            urllib.request.urlopen(req, timeout=10)
            return True
        except Exception:
            return False

    def complete(self, prompt: str, timeout: int = 900) -> str:
        body = json.dumps(
            {
                "model": self.model or "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            }
        ).encode()
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"openai backend HTTP {exc.code}: {exc.read().decode()[:300]}")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"openai backend unreachable at {self.base_url}: {exc}")
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"openai backend returned unreadable response: {exc}")


class CommandBackend(Backend):
    """Any shell command where {prompt} is replaced with the prompt text."""

    def __init__(self, template: str):
        self.template = template
        self.name = f"cmd:{template[:40]}"

    def probe(self) -> bool:
        # Can't cheaply probe a raw command; assume reachable if requested.
        return True

    def complete(self, prompt: str, timeout: int = 900) -> str:
        cmd = self.template.replace("{prompt}", prompt)
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(
                f"command backend failed: {(proc.stderr or proc.stdout).strip()[:500]}"
            )
        return proc.stdout.strip()


def _routes() -> list[Backend]:
    """Ordered candidate routes: opencode, claude, openai, custom command."""
    routes: list[Backend] = [OpenCodeBackend(), ClaudeCliBackend(), OpenAIBackend()]
    custom = os.environ.get("GTA6_CLIPPER_LLM_COMMAND")
    if custom:
        routes.append(CommandBackend(custom))
    return routes


def get_backend(spec: str = "auto", model: str | None = None) -> Backend:
    """Resolve a backend spec to a concrete route.

    Specs: ``opencode``, ``claude``, ``openai``, ``cmd:<template>``, ``auto``.
    ``auto`` probes each route in order and picks the first that answers.
    """
    spec = (spec or "auto").strip()

    if spec == "cmd" or spec == "":
        raise ValueError("use --backend cmd:'<template>' with a command, e.g. cmd:'ollama run qwen3.5:27b {prompt}'")

    if spec.startswith("cmd:"):
        return CommandBackend(spec[len("cmd:") :])

    if spec == "auto":
        for route in _routes():
            try:
                if route.probe():
                    return route
            except Exception:
                continue
        raise RuntimeError(
            "no LLM backend available. Install opencode or the claude CLI, "
            "or run an OpenAI-compatible endpoint (LM Studio, llama.cpp, Ollama /v1) "
            "and set GTA6_CLIPPER_LLM_BASE_URL / GTA6_CLIPPER_LLM_MODEL."
        )

    known = {"opencode": OpenCodeBackend, "claude": ClaudeCliBackend, "openai": OpenAIBackend}
    if spec not in known:
        raise ValueError(
            f"unknown backend: {spec}. Use opencode, claude, openai, cmd:'<template>', or auto."
        )
    route = known[spec]()
    if not route.probe():
        raise RuntimeError(
            f"{spec} backend requested but not reachable. "
            "Install it or pick another backend."
        )
    return route


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
