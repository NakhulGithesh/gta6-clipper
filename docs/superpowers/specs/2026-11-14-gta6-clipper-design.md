# GTA 6 Clipper — Design Spec

Date: 2026-11-14
Source: https://youtu.be/5-SDYLlGZFw ("How to Make Money Clipping GTA 6 Videos (Turned Into A Free Skill)", Jad M.H | AI Automation)

## Purpose

A standalone opencode/Claude skill that turns a long game reaction stream into ready-to-post
vertical clips, automatically. Same job the video's free skill does: download audio only,
transcribe locally, detect the loud moments, let an LLM pick and score the shareable ones, then
render vertical clips with facecam on top, word-by-word captions, a hook title and a post caption.

## Decisions (from user)

| Question | Answer |
|---|---|
| Platform | macOS only |
| Distribution | Local copy in `/Users/nakhulgithesh/Documents/work/shorts/gta6-clipper` + publishable skill package (GitHub repo, `npx skills add`) |
| Scope | Full implementation, not a stub |
| Relation to other projects | Fully standalone; no integration with the drilling simulator |

## Constraints from the source video

- No API keys required for the free path; local models only.
- Mac only for now (facecam detection, brew-based setup).
- Age-restricted YouTube streams and Kick need browser cookies (`--cookies chrome`).
- YouTube may refuse monetization for reposted mass-made content: add something of your own.
- Clip only streamers whose clipping program allows it; watch every clip before posting.

## Architecture

```
gta6-clipper/
├── SKILL.md                  # agent-facing instructions (the "skill" the video talks about)
├── skill.json                # manifest (name, version, entrypoints, requirements)
├── README.md                 # human docs, install, publish, ethics
├── LICENSE                   # MIT
├── NOTICE                    # attribution for vendored/inspired work
├── GATES.md                  # acceptance ledger (unlazy)
├── bin/gta6-clipper          # CLI entrypoint (python3 -m)
├── src/gta6clipper/
│   ├── cli.py                # subcommands: setup | clip | auto-clip | status | doctor
│   ├── config.py             # paths, settings, mode selection
│   ├── fetch.py              # yt-dlp: audio-only, metadata, video segments, live search
│   ├── transcribe.py         # whisper.cpp primary, YouTube auto-subs fallback
│   ├── loudness.py           # RMS envelope from decoded PCM -> peaks
│   ├── chat.py               # optional YouTube live-chat replay -> message velocity
│   ├── moments.py            # candidate windows: loud peaks + chat spikes + transcript
│   ├── llm.py                # backends: claude CLI, ollama; prompt build + JSON parse
│   ├── rubric.py             # scoring rubric, moment types, harsh filters
│   ├── facecam.py            # YuNet face detection -> corner-anchored inset box
│   ├── captions.py           # ASS generation: word-by-word + hook title
│   ├── ffmpeg.py             # filtergraph builder: vertical fit, facecam overlay, loudnorm
│   ├── render.py             # orchestrator for clip rendering
│   └── find_streams.py       # discover today's biggest game reaction streams
├── tests/                    # pytest, pure logic + ffmpeg integration
└── scripts/                  # setup.sh (brew installs, model downloads), verify_*.py
```

### Pipeline (the video's four steps, one function each)

1. **Fetch** — `yt-dlp` fetches audio only (`-f ba`). A 4h stream is a few hundred MB, not a
   multi-GB video. Video bytes are pulled later, and only for the chosen minutes
   (`--download-sections`).
2. **Listen** — `whisper.cpp` transcribes locally to JSON with word timings. Two extra signals are
   recorded while the audio is decoded: where the streamer got loud (RMS envelope peaks) and,
   when available, where YouTube chat sped up (messages per second). YouTube auto-captions are the
   fallback when whisper.cpp is unavailable.
3. **Pick** — the transcript is read in 12-minute windows. The LLM (Claude Code CLI or a local
   Ollama model) finds moments of the video's five types (first reaction, crazy discovery,
   freakout, funny fail, hot take), scores each 0-100, and rejects anything that needs context or
   opens on filler. Strict JSON in, validated JSON out.
4. **Render** — for each kept moment: download only that minute range, detect the facecam box
   (YuNet + corner anchoring), build a 1080x1920 ffmpeg filtergraph (blurred backdrop, gameplay
   centred, facecam pinned top), burn word-by-word captions and the hook title, normalise audio to
   -14 LUFS, and write a post caption with hashtags beside it.

### Mode matrix

| Mode | LLM backend | Needs | Notes |
|---|---|---|---|
| `claude` (default) | `claude -p` CLI | Claude subscription | Best picks, fastest. No API key. |
| `ollama` | `ollama run qwen3.5:27b` | Ollama + model | Free. 16 GB RAM -> qwen3.5:9b, 32 GB+ -> qwen3.5:27b. Slower, rougher picks. |

Transcription is always local (whisper.cpp). Chat velocity is optional and degrades silently to
"not available" when `youtube-chat-downloader` is not installed.

### CLI

```bash
gta6-clipper setup [--mode claude|ollama|both]   # deps, models, checks
gta6-clipper doctor                              # what is missing, exact fix command
gta6-clipper clip <url> [--out DIR] [--clips N] [--mode claude|ollama] [--cookies chrome]
gta6-clipper auto-clip [--count N] [--out DIR]   # find today's biggest streams, clip them
gta6-clipper status                               # last run, output location, pending clips
```

### Output

```
<out>/<streamer-slug>/
├── meta.json            # source URL, title, channel, duration, mode
├── transcript.json      # words with timings
├── moments.json         # scored candidates (all, including rejected)
├── clips.json           # kept clips with hook/title/caption/hashtags
├── clip-01.mp4 ...      # 1080x1920 renders
└── clip-01.post.txt     # caption + hashtags, ready to paste
```

## Error handling

- Missing dependency -> `doctor` prints the exact install command; `setup` runs it.
- Download blocked (age gate) -> retry once with `--cookies chrome` and report clearly.
- No facecam found -> render gameplay-only vertical, note it in `clips.json` (`facecam: null`).
- LLM returns malformed JSON -> one repair attempt, then fail the scoring stage with the raw
  output saved. Never invent clips.
- Ollama not running -> fail with `ollama serve` hint; no silent fallback to a cloud API.

## Testing

- `tests/`: pure logic (loudness peaks, windowing, dedup, rubric validation, JSON parsing, ASS
  generation, filtergraph strings, facecam box geometry) plus one ffmpeg integration test that
  renders a 2-second synthetic clip.
- End-to-end: run the real pipeline on a public short video and assert that an mp4, `clips.json`
  and a post caption are produced.

## Ethics / guardrails (from the video, enforced in SKILL.md)

- Only clip streamers whose clipping program permits it; credit the streamer.
- Watch every clip before posting.
- YouTube Partner Program eligibility is the user's business; mass-reposted content can be
  demonetised, so add original framing.

## Publish path

- Git repo in `gta6-clipper/` with MIT license.
- `npx skills add NakhulGithesh/gta6-clipper` after push (skills CLI has no publish command).
- Local install: copy or symlink into `~/.agents/skills/gta6-clipper` (opencode) or
  `~/.claude/skills/gta6-clipper` (Claude Code).
