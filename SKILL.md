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
  money clipping game streams. Two ways to run it: a Claude subscription (best picks) or a free
  local Ollama model (no API key). macOS only. Clips only what the user may use, and nothing
  posts without their yes.
metadata:
  version: 1.0.0
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
bin/gta6-clipper setup --mode claude    # or --mode ollama, or --mode both
bin/gta6-clipper doctor
```

`setup` installs ffmpeg, yt-dlp and whisper.cpp with Homebrew, downloads the whisper model and
the facecam model, and (for the free route) Ollama with a local model. `doctor` reports anything
missing with the exact fix command.

Pick the route:

| Route | Needs | Cost | Picks |
|---|---|---|---|
| `claude` (default) | Claude Code CLI on a subscription | $20/month | Best, fastest. No API key. |
| `ollama` | Ollama + `qwen3.5:27b` (32 GB+ RAM) or `qwen3.5:9b` (16 GB) | Free | Slower, rougher, needs more back and forth |

Be honest with the user about the difference: the free model is not Claude. It still beats
scrubbing a stream by hand.

## Step 1: Clip a stream

```bash
bin/gta6-clipper clip "<stream url>" --out ./clips
```

Options that matter:

- `--cookies chrome` for age-restricted YouTube streams and Kick. Needed for most GTA streams.
- `--clips 3` how many clips to keep (default 3).
- `--mode claude|ollama` which backend scores the moments.
- `--no-render` stop after scoring, when the user only wants to see the picks.

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

Output lands in `<out>/<streamer>/`: `clip-01.mp4`, `clip-01.post.txt` (caption and hashtags),
`clips.json`, `moments.json`, `transcript.json`, `meta.json`.

## Step 2: Find the streams yourself

```bash
bin/gta6-clipper auto-clip --count 7 --out ./clips
```

Finds today's biggest GTA 6 reaction streams and clips each one. Seven streams is roughly a day's
of posting. Before launch day, this is the window: everybody watches the same reactions at the
same time, and whoever has the clips ready wins.

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
- The free Ollama route gives rougher picks. If the user earns from this, get the subscription.
- YouTube Partner Program eligibility: 1,000 subscribers and 4,000 watch hours in 12 months, or
  10 million Shorts views in 90 days.

## References

- `references/rubric.md` - the moment types, the score, and what gets thrown away.
- `references/setup.md` - installing the free route, memory to model, and the Claude route.
- `references/platform-notes.md` - cookies, age gates, clipping programs, monetisation.
