# Setup

macOS only. `bin/gta6-clipper setup` installs the binaries, models and Python deps; it installs
no LLM server. Pick your scoring backend at clip time with `--backend`.

## What gets installed

| Thing | Why | Installed by |
|---|---|---|
| ffmpeg / ffprobe | decoding, rendering, loudness | `brew install ffmpeg` |
| yt-dlp | audio-only and section downloads | `brew install yt-dlp` |
| whisper.cpp | local transcription with word timings | `brew install whisper.cpp` |
| `ggml-large-v3-turbo.bin` | the speech model, about 1.6 GB | downloaded into `~/.cache/gta6-clipper/models` |
| `face_detection_yunet_2023mar.onnx` | facecam detection, about 230 KB | same folder |
| Python venv | numpy, opencv-python, Pillow | created at `~/.cache/gta6-clipper/venv` |

Nothing is installed system-wide without Homebrew's own prompts. The models land in
`~/.cache/gta6-clipper/models` and the Python packages in `~/.cache/gta6-clipper/venv`, both of
which can be moved with `GTA6_CLIPPER_CACHE`.

The Python venv is deliberate: Homebrew upgrades its Python without warning, and a skill that
depends on `pip install --user` breaks the next time that happens.

## Picking a backend

The clipper runs the scoring LLM through a pluggable backend. Choose one with `--backend`:

| Backend | `--backend` value | Cost | Notes |
|---|---|---|---|
| `opencode` | `opencode` | Free / subscription | opencode CLI |
| `claude` | `claude` | $20/month | Claude Code CLI |
| `openai` | `openai` | Depends | Any OpenAI-compatible endpoint |
| `cmd:<template>` | `cmd:'<template>'` | Depends | Any shell command with `{prompt}` |
| `auto` (default) | `auto` | Depends | Probes opencode → claude → openai → `GTA6_CLIPPER_LLM_COMMAND` |

### OpenAI-compatible endpoint (free local route with LM Studio)

Leave LM Studio (or llama.cpp / Ollama /v1 / vLLM) running, then:

```bash
GTA6_CLIPPER_LLM_BASE_URL=http://localhost:1234/v1 \
GTA6_CLIPPER_LLM_MODEL=qwen3.8-27b-uncensored-mlx \
bin/gta6-clipper clip "<url>" --backend openai
```

No API key needed for local endpoints. Only set `GTA6_CLIPPER_LLM_API_KEY` if the endpoint
requires one.

### Ollama (still works)

Ollama isn't installed or hardcoded anymore — it's just another command:

```bash
bin/gta6-clipper clip "<url>" --backend "cmd:ollama run qwen3.5:27b {prompt}"
```

Model size follows your memory, not your disk: 16 GB RAM → `qwen3.5:9b`, 32 GB+ →
`qwen3.5:27b`. More memory = sharper picks.

### Custom command

Any command where `{prompt}` is replaced with the scoring prompt:

```bash
bin/gta6-clipper clip "<url>" --backend "cmd:llama-cli -p {prompt}"
```

## Cookies

Age-restricted YouTube streams (most GTA streams) and Kick need your browser login:

```bash
bin/gta6-clipper clip "<url>" --cookies chrome
```

`--cookies-from-browser chrome` reads the cookies from the installed Chrome profile. Use
`firefox`, `safari` or `edge` instead if that is your browser.

## Checking the install

```bash
bin/gta6-clipper doctor
```

Reports every dependency, the model files and each backend route, with the exact fix command for
anything missing. `doctor --json` prints the same as JSON. LLM backends are optional: only the
one you use has to be reachable.
