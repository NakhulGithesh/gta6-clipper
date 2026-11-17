---
name: gta6-clipper
description: >-
  Turn a long game reaction stream into ready-to-post vertical clips, automatically. Give it a
  YouTube, Twitch or Kick stream link (or nothing, and it finds today's biggest GTA 6 streams),
  and it downloads only the audio, transcribes it locally, finds the loud moments, lets an LLM
  score and pick the shareable ones, then renders 1080x1920 clips with the facecam on top, the
  gameplay underneath, word-by-word captions, a hook title and a post caption with hashtags.
  Use when someone says "clip GTA 6", "clip this stream", "make clips from this reaction
  stream", "find today's biggest GTA 6 streams and clip them", "AI clipper", or asks how to make
  money clipping game streams. The scoring LLM is pluggable: opencode, claude, or any
  OpenAI-compatible endpoint (LM Studio, llama.cpp server, Ollama /v1, vLLM, cloud API, or a
  custom command). macOS only. Clips only what the user may use, and nothing posts without their yes.
metadata:
  version: 1.1.0
license: MIT
---

# GTA 6 Clipper

A four hour reaction stream holds a week of clips if you can find the right minute. Finding that
minute by hand means scrubbing the whole thing while waiting for something to happen. This skill
does the finding: it listens to the stream, marks where the streamer lost it, and lets an LLM
pick the moments that work on their own.

Four commitments:

1. **Only footage the user may use.** Their own stream, or a streamer whose clipping program
   allows it. Ask before clipping anyone.
2. **Nothing posts without a yes.** Show the clips, titles, captions and hashtags first.
3. **The audio stays local.** Transcription runs on the machine. No API keys for the free route.
4. **No invented claims.** Hooks and captions say what the clip says.

## Step 0: Setup

```bash
bin/gta6-clipper setup
bin/gta6-clipper doctor
```

`setup` installs ffmpeg, yt-dlp and whisper.cpp with Homebrew, creates a Python virtualenv in
`~/.cache/gta6-clipper/venv` with numpy, opencv and Pillow, and downloads the whisper model and
the facecam model. `doctor` reports anything missing with the exact fix command.

Setup installs **no LLM server** — the clipper doesn't require one. Pick your scoring backend at
clip time:

| Backend | `--backend` value | Cost | Notes |
|---|---|---|---|
| `opencode` | `opencode` | Free / subscription | opencode CLI, `opencode run <prompt>` |
| `claude` | `claude` | $20/month | Claude Code CLI, no API key |
| `openai` | `openai` | Depends | Any OpenAI-compatible endpoint (LM Studio, llama.cpp, Ollama /v1, vLLM, cloud) |
| `cmd:<template>` | `cmd:'<template>'` | Depends | Any shell command with `{prompt}` |
| `auto` (default) | `auto` | Depends | Probes opencode → claude → openai endpoint → `GTA6_CLIPPER_LLM_COMMAND`; if a route fails at call time it falls through to the next |

OpenAI-compatible env vars:

- `GTA6_CLIPPER_LLM_BASE_URL` — default `http://localhost:1234/v1` (LM Studio)
- `GTA6_CLIPPER_LLM_MODEL` — model name, e.g. `qwen3.8-27b-uncensored-mlx`
- `GTA6_CLIPPER_LLM_API_KEY` — only if the endpoint requires one

The opencode CLI is found on `PATH`, at `/Applications/OpenCode.app/Contents/Resources/opencode-cli`
(the desktop app's bundled CLI), or wherever `OPENCODE_CLI` points.

Your LM Studio model is a free local route — just leave LM Studio running and use `--backend openai`. No Ollama install needed.

## Step 1: Clip a stream

```bash
bin/gta6-clipper clip "<stream url>" --out ./clips
```

Options that matter:

- `--cookies chrome` for age-restricted YouTube streams and Kick. Needed for most GTA streams.
- `--clips 3` how many clips to keep (default 3).
- `--backend claude|openai|opencode|cmd:'<template>'|auto` which LLM scores the moments.
- `--no-render` stop after scoring, when the user only wants to see the picks.

Examples:

```bash
# free, local, via LM Studio (leave LM Studio running)
bin/gta6-clipper clip "<url>" --backend openai

# via opencode CLI
bin/gta6-clipper clip "<url>" --backend opencode

# via Claude subscription
bin/gta6-clipper clip "<url>" --backend claude

# via any command (e.g. ollama)
bin/gta6-clipper clip "<url>" --backend "cmd:ollama run qwen3.5:27b {prompt}"
```

## Live / ongoing streams

For a stream that is **live right now**, `clip` won't work because the download never finishes. Use `live` instead:

```bash
# Record 1 hour of a live stream, then clip the good moments
bin/gta6-clipper live "<stream url>" --duration 3600 --out ./clips

# Record 30 minutes, 3 clips
bin/gta6-clipper live "<stream url>" --duration 1800 --clips 3 --out ./clips

# Age-restricted streams need cookies
bin/gta6-clipper live "<url>" --duration 3600 --cookies chrome
```

`live` records audio for the fixed duration (ffmpeg stops automatically), then runs the same scoring and rendering pipeline on that recording. A 1-hour recording yields roughly the same output as a 1-hour VOD.

Twitch live streams work the same way; Kick needs `--cookies chrome`.

The pipeline does the video's four steps:

1. **Audio only.** A four hour stream is a few hundred MB, not a few GB.
2. **Listen locally.** whisper.cpp transcribes it; the loudness envelope marks where the streamer
   got loud, and YouTube chat speed is used too when that route is available.
3. **Pick.** The transcript is read in twelve minute windows. The LLM finds first reactions,
   crazy discoveries, freakouts, funny fails and hot takes, scores each, and drops anything that
   needs context or opens on filler.
4. **Render.** Only the chosen minutes are downloaded. The facecam is found automatically, the
   clip becomes 1080x1920 with the facecam on top and the gameplay underneath, word-by-word
   captions and the hook title are burned in, and audio is normalised to -14 LUFS.

Captions are drawn with Pillow into a transparent layer that ffmpeg overlays, because Homebrew's
ffmpeg has no libass and no drawtext. Nothing about the captions depends on the ffmpeg build.

Output lands in `<out>/<streamer>/`: `clip-01.mp4`, `clip-01.post.txt` (caption and hashtags),
`clips.json`, `moments.json`, `transcript.json`, `meta.json`.

## Step 2: Find the streams yourself

```bash
bin/gta6-clipper auto-clip --count 7 --out ./clips
```

Finds today's biggest GTA 6 reaction streams and clips each one: live streams first, then the
biggest recent reaction VODs longer than ten minutes. `--live-only` restricts it to streams that
are live right now. Seven streams is roughly a day's of posting. Before launch day, this is the
window: everybody watches the same reactions at the same time, and whoever has the clips ready
wins.

## Step 3: Review before posting

Open every rendered clip. Then show the user a table: file, hook line, title, caption, hashtags.
Wait for their yes before anything is posted. The clipper writes files; publishing is a separate
step (use the `publish` skill if the user wants it posted).

Checklist before posting:

- The streamer allows clipping. Many big streamers run clipping programs that pay per view; ask
  for the brief, and credit them.
- The clip stands alone: a stranger understands it with no context.
- YouTube monetisation is the user's business. YouTube can refuse Partner Program money for
  reposted, mass-made content, so the clip needs something of the user's own around it.

## What the user should know

- Mac only.
- Age-restricted streams and Kick need `--cookies chrome`.
- If you want free local scoring, run an OpenAI-compatible endpoint (LM Studio, llama.cpp,
  Ollama /v1) and use `--backend openai`. Ollama still works via
  `--backend "cmd:ollama run MODEL {prompt}"`.
- YouTube Partner Program eligibility: 1,000 subscribers and 4,000 watch hours in 12 months, or
  10 million Shorts views in 90 days.

## References

- `references/rubric.md` - the moment types, the score, and what gets thrown away.
- `references/setup.md` - what setup installs, and how to point the clipper at your LLM.
- `references/platform-notes.md` - cookies, age gates, clipping programs, monetisation.
