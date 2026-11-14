# Platform notes

## Age restricted streams and Kick

GTA reaction streams are usually age restricted, and Kick needs a login. Both are handled by
passing the browser:

```bash
bin/gta6-clipper clip "<url>" --cookies chrome
```

If the download fails with an age gate error, this is the fix. It is not a bug.

## Clipping programs

Most large streamers run a clipping program: a set of rules, usually a brief of what can be
clipped, and a payment per view or per clip. Clipping is not the same as reposting a full video.

Before clipping anyone:

- check whether they run a clipping program and what the brief allows
- credit the streamer
- do not clip private or off-platform material

This skill does not post anything. It writes files and captions for the user to review and post
themselves.

## YouTube monetisation

The Partner Program needs 1,000 subscribers and 4,000 watch hours in 12 months, or 10 million
Shorts views in 90 days.

More important: YouTube can refuse Partner Program money for reposted, mass-made content. A
folder of forty identical clips from one streamer is exactly what that policy targets. The fix is
not technical: add something of your own around the clip (your own voice, your own framing, a
point of view), and post fewer, better clips.

## Twitch and Kick

Twitch and Kick streams are supported through yt-dlp. Twitch live chat is not used for the chat
spike signal, and Kick needs browser cookies. Twitch VODs and clips on YouTube work normally.

## The chat signal

Chat velocity (messages per second) is an optional second signal on top of loudness. It needs the
`youtube-chat-downloader` package:

```bash
pip install youtube-chat-downloader
```

Without it, the pipeline runs on loudness and the LLM's read of the transcript, which is enough.
It never fails because chat is unavailable.

## Performance notes

- Audio-only download of a four hour stream: a few hundred MB.
- whisper.cpp with `large-v3-turbo` on an Apple Silicon Mac: roughly real time or faster.
- Rendering a clip downloads only that minute range, so the video bytes for a full stream never
  hit the disk.
- The facecam detector samples 10 frames per clip, so it costs seconds, not minutes.
