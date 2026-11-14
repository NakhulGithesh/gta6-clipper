# Setup

macOS only. `bin/gta6-clipper setup --mode both` does everything; this page is what it does and
why, plus how to do it by hand.

## What gets installed

| Thing | Why | Installed by |
|---|---|---|
| ffmpeg / ffprobe | decoding, rendering, loudness | `brew install ffmpeg` |
| yt-dlp | audio-only and section downloads | `brew install yt-dlp` |
| whisper.cpp | local transcription with word timings | `brew install whisper-cpp` |
| `ggml-large-v3-turbo.bin` | the speech model, about 1.6 GB | downloaded into `~/.cache/gta6-clipper/models` |
| `face_detection_yunet_2023mar.onnx` | facecam detection, about 350 KB | same folder |
| Ollama + model | the free local LLM route | `brew install ollama`, optional |

Nothing is installed system-wide without Homebrew's own prompts. The models land in
`~/.cache/gta6-clipper/models`, which can be moved with `GTA6_CLIPPER_CACHE`.

## Route 1: Claude (recommended)

```bash
bin/gta6-clipper setup --mode claude
```

Needs the Claude Code CLI on a subscription ($20/month starts). No API key: the skill drives the
`claude` CLI, which uses the subscription you already pay for. Best picks, fastest turnaround.

## Route 2: Ollama (free)

```bash
brew install ollama
ollama serve
```

Then, in another terminal:

```bash
ollama pull qwen3.5:27b
```

Model size follows your memory, not your disk. Check memory with the Apple menu, About This Mac,
Memory:

| Memory | Model | Note |
|---|---|---|
| 16 GB | `qwen3.5:9b` | usable, rougher picks |
| 32 GB or more | `qwen3.5:27b` | sharper picks |

Then use it:

```bash
bin/gta6-clipper setup --mode ollama
bin/gta6-clipper clip "<url>" --mode ollama
```

Honest comparison: the free model is not Claude. It is slower, its picks are rougher, and expect
back and forth before a clip is good enough. It still beats scrubbing a four hour stream by hand.

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

Reports every dependency, the model files and both LLM backends, with the exact fix command for
anything missing. `doctor --json` prints the same as JSON.
