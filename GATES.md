# Gates: gta6-clipper skill

OWNS: src/**, tests/**, scripts/**, bin/**, SKILL.md, skill.json, README.md, LICENSE, NOTICE, docs/**

Scope: A standalone macOS skill that turns a long game reaction stream into ready-to-post vertical clips, plus a publishable skill package.

- [ ] G1: Unit suite green, every pure-logic module covered
  CHECK: python3 -m pytest -q tests
  EXPECT: PASSED

- [ ] G2: Skill package is structurally valid and installable
  CHECK: python3 scripts/verify_package.py
  EXPECT: PACKAGE OK

- [ ] G3: Moment scoring produces validated, rubric-conformant clips from a transcript
  CHECK: python3 scripts/verify_scoring.py
  EXPECT: SCORING OK

- [ ] G4: End-to-end pipeline turns a real public video into mp4 clips plus post captions
  CHECK: python3 scripts/verify_e2e.py
  EXPECT: E2E OK

- [ ] G5: Setup is idempotent and doctor reports every dependency with a fix command
  CHECK: bash scripts/setup.sh --check && PYTHONPATH=src python3 -m gta6clipper.cli doctor --json
  EXPECT: SETUP OK

- [ ] G6: Rendered clip is visually correct (facecam on top, captions readable, 1080x1920)
  EVIDENCE: pending

- [ ] G7: Skill is published and installable by others
  EVIDENCE: pending
