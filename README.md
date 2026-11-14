# GTA 6 Clipper

A skill that turns a long game reaction stream into ready-to-post vertical clips, automatically.

Give it a YouTube, Twitch or Kick stream link. It downloads only the audio, transcribes it on your
machine, finds where the streamer got loud, lets an LLM score and pick the moments worth sharing,
and renders 1080x1920 clips with the facecam on top, the gameplay underneath, word-by-word
captions, a hook title and a post caption with hashtags.

macOS only. Two ways to run the scoring: a Claude subscription (best picks) or a free local Ollama
model (no API key).

## Install

```bash
git clone https://github.com/NakhulGithesh/gta6-clipper.git
cd gta6-clipper
bin/gta6-clipper setup --mode claude      # or --mode ollama, or --mode both
bin/gta6-clipper doctor
```

Or, as a skill in another agent:

```bash
npx skills add NakhulGithesh/gta6-clipper
```

## Use

```bash
# clip one stream
bin/gta6-clipper clip "https://www.youtube.com/watch?v=..." --out ./clips

# age restricted streams and Kick
bin/gta6-clipper clip "<url>" --cookies chrome

# find today's biggest GTA 6 streams and clip them
bin/gta6-clipper auto-clip --count 7 --out ./clips

# only what is live right now
bin/gta6-clipper auto-clip --count 7 --live-only

# what has been clipped
bin/gta6-clipper status --out ./clips
```

Output per stream:

```
clips/<streamer>/
├── clip-01.mp4          1080x1920, facecam on top, captions burned in
├── clip-01.post.txt     caption and hashtags, ready to paste
├── clips.json           what was rendered
├── moments.json         every candidate, what was kept and what was rejected
├── transcript.json      every word with its timing
└── meta.json            source, channel, duration
```

## How it works

1. **Audio only.** A four hour stream is a few hundred MB, not a few GB.
2. **Listen locally.** whisper.cpp transcribes with word timings. The RMS envelope marks where the
   streamer got loud; YouTube chat speed is used too when that route is available.
3. **Pick.** The transcript is read in twelve minute windows. The LLM finds first reactions, crazy
   discoveries, freakouts, funny fails and hot takes, scores each, and drops anything that needs
   context or opens on filler.
4. **Render.** Only the chosen minutes are downloaded. The facecam is found automatically (YuNet
   face detection plus corner anchoring), the clip becomes vertical, captions and hook are burned
   in, audio is normalised to -14 LUFS.

A four hour stream with 39 candidate moments becomes three ready clips. Seven streams is roughly a
day of posting.

## Requirements

- macOS, Python 3.10+
- ffmpeg, ffprobe, yt-dlp, whisper.cpp (`bin/gta6-clipper setup` installs them)
- numpy, opencv-python and Pillow, installed by setup into `~/.cache/gta6-clipper/venv`
- a scoring backend: Claude Code CLI, or Ollama with a local model

Captions are drawn with Pillow into a transparent layer that ffmpeg overlays, so the skill works
with Homebrew's ffmpeg even though that build has no libass and no drawtext.

## Free route

| Memory | Model |
|---|---|
| 16 GB | `qwen3.5:9b` |
| 32 GB or more | `qwen3.5:27b` |

The free model is not Claude: slower, rougher picks. It still beats scrubbing a stream by hand.

## Before you post

- Clip only streamers whose clipping program allows it, and credit them.
- Watch every clip before posting. This skill writes files; it does not post.
- YouTube can refuse Partner Program money for reposted, mass-made content. Add something of your
  own around the clip.

## Development

```bash
~/.cache/gta6-clipper/venv/bin/python -m pytest -q tests   # unit suite
~/.cache/gta6-clipper/venv/bin/python scripts/verify_package.py   # package structure
~/.cache/gta6-clipper/venv/bin/python scripts/verify_scoring.py   # rubric and scoring plumbing
~/.cache/gta6-clipper/venv/bin/python scripts/verify_e2e.py       # real video to real clips
```

## License

MIT. See `LICENSE` and `NOTICE`.
