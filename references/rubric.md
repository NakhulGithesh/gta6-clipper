# The rubric: what makes a clip worth posting

The LLM reads the stream in twelve minute windows and returns JSON. This is the rubric it is given,
and the rubric the skill enforces again on the way out. Nothing that fails the second pass is ever
rendered.

## Moment types

| Type | What it is | Example |
|---|---|---|
| `first_reaction` | The very first reaction to something, said out loud | "Okay wait, they added what?" |
| `crazy_discovery` | Finding something nobody expected | "There is a whole city under the bridge?" |
| `freakout` | Losing control: screaming, or dead silent in shock | silence for four seconds, then "NO" |
| `funny_fail` | Something going hilariously wrong | the car falls off the bridge, again |
| `hot_take` | A strong opinion that sparks argument | "This is the worst GTA ever" |

## What gets thrown away

- Anything that needs context from earlier in the stream.
- Anything that starts with filler: "uh", "so yeah", "wait hold on", "anyway".
- Talking, setup, dead air, sponsor reads.
- Anything that would not be funny, shocking or arguable as a standalone clip.

## Score

0 to 100, and the instruction is to be harsh. Below 70 is not worth posting. The score weighs:

- the first three seconds (hook or no hook)
- whether it lands without context
- the size of the reaction
- whether it is a specific, shareable claim rather than a general mood

## Length

20 to 60 seconds by default, 90 seconds maximum. A clip that needs more than a minute of setup is
a clip that needs context.

## Hard rules the pipeline checks

- `start` and `end` in whole seconds of the original stream, `end` after `start`.
- `type` is one of the five above.
- `score` between 0 and 100.
- `hook` is 3 to 8 words, under 80 characters.
- `title` under 100 characters.
- 3 to 8 hashtags, each starting with `#`.
- `needs_context` and `starts_with_filler` both false.

A moment that fails any of these is dropped and reported in `moments.json` under `rejected`, so a
weak model can be spotted instead of silently trusted.
