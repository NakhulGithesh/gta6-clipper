# Gates: gta6-clipper skill

OWNS: src/**, tests/**, scripts/**, bin/**, SKILL.md, skill.json, README.md, LICENSE, NOTICE, docs/**

Scope: A standalone macOS skill that turns a long game reaction stream into ready-to-post vertical clips, plus a publishable skill package.

- [x] G1: Unit suite green, every pure-logic module covered
  CHECK: "$HOME/.cache/gta6-clipper/venv/bin/python" -m pytest -q tests && echo "UNIT OK"
  EXPECT: UNIT OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=c3eebbd86c22c314f80e62d2c89415f835704bc9ed3e73ce942863d410d0368d; exit=0; EXPECT=matched; output-sha256=39b772ca5f1614473dc94bf91a283f9283c5bbba88fdea68a70395cc117cee14; output-bytes=187; shell=/bin/sh; cwd=/Users/nakhulgithesh/Documents/work/shorts/gta6-clipper; path=de9ffc55b979/23 entries

- [x] G2: Skill package is structurally valid and installable
  CHECK: "$HOME/.cache/gta6-clipper/venv/bin/python" scripts/verify_package.py
  EXPECT: PACKAGE OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=a71d870c57fd57d88a5cb2ff2fc4d98af7ae87a8c8666cf95770f1dd54742a90; exit=0; EXPECT=matched; output-sha256=cf1db73e57cb4ad7390f42714adf3573ded2bca69c50cf2af4175e645f48560b; output-bytes=11; shell=/bin/sh; cwd=/Users/nakhulgithesh/Documents/work/shorts/gta6-clipper; path=de9ffc55b979/23 entries

- [x] G3: Moment scoring produces validated, rubric-conformant clips from a transcript
  CHECK: "$HOME/.cache/gta6-clipper/venv/bin/python" scripts/verify_scoring.py
  EXPECT: SCORING OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=486b396744715728b7b9bf0e44cb284361dd80d8bc7f577888075270886eea7a; exit=0; EXPECT=matched; output-sha256=adb1d1492737eae310cf182af37c37fe9d4415302d4669a71b43804efc5a2006; output-bytes=11; shell=/bin/sh; cwd=/Users/nakhulgithesh/Documents/work/shorts/gta6-clipper; path=de9ffc55b979/23 entries

- [x] G4: End-to-end pipeline turns a real public video into mp4 clips plus post captions
  CHECK: "$HOME/.cache/gta6-clipper/venv/bin/python" scripts/verify_e2e.py
  EXPECT: E2E OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=77cdcaff9c77514934c508116c7bcf0491a73d634d62babebff4c6b73a23abe7; exit=0; EXPECT=matched; output-sha256=083c7455992249dfc040cac0d45abf1044586038e7b5d2c584d6ae5558971f76; output-bytes=688; shell=/bin/sh; cwd=/Users/nakhulgithesh/Documents/work/shorts/gta6-clipper; path=de9ffc55b979/23 entries

- [x] G5: Setup is idempotent and doctor reports every dependency with a fix command
  CHECK: bash scripts/setup.sh --check && bin/gta6-clipper doctor --json
  EXPECT: SETUP OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=6d12c6eedcebcaea67d834944407913473be65f9017c7dbb3e1ff4cb795554a3; exit=0; EXPECT=matched; output-sha256=a21d2ed2b4d96674b0547776f1fac6e031658b3744d1222af1881b688982e4af; output-bytes=2121; shell=/bin/sh; cwd=/Users/nakhulgithesh/Documents/work/shorts/gta6-clipper; path=de9ffc55b979/23 entries

- [x] G6: Rendered clip is visually correct (facecam placement and caption legibility)
  EVIDENCE: 2026-11-14. Inspected frames of two renders of a real video
  (demo/how-to-make-money-clipping-gta-6-videos-turned-into-a-free-s/):
  clip-01.mp4 = gameplay-only layout, hook wraps to two lines inside the margins, word-by-word
  caption with the active word in yellow, blurred backdrop, 1080x1920 (frames/frame-1.png,
  frames/frame-12.png); clip-02.mp4 = facecam layout, YuNet found the inset at
  (1448, 784, 330, 186) and it is placed on top with the gameplay underneath
  (frames2/frame-12.png).

- [x] G7: Skill is published and installable by others
  EVIDENCE: 2026-11-14. Public repo https://github.com/NakhulGithesh/gta6-clipper pushed from
  commit d32ae22; `npx skills add NakhulGithesh/gta6-clipper -y` in a clean directory installed
  .agents/skills/gta6-clipper with SKILL.md, scripts, references, src and bin.

- [x] G8: Live stream recording works end-to-end with mocked network
  CHECK: "$HOME/.cache/gta6-clipper/venv/bin/python" scripts/verify_live.py
  EXPECT: LIVE OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=dd227790aff478eb83778eaa53e9714c7d72c461627d1dd6fcfc81979cb6546c; exit=0; EXPECT=matched; output-sha256=8eb133fc50b03a1d0a51c8320280ef73ea6c875fe234a6358e194eafec044956; output-bytes=451; shell=/bin/sh; cwd=/Users/nakhulgithesh/Documents/work/shorts/gta6-clipper; path=de9ffc55b979/23 entries
