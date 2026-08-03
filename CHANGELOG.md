# Changelog

Notable changes to Transit Label Tuner are recorded here.

## [0.1.0] — 2026-08-03

Initial public release candidate.

### Added

- Single-file, dependency-free transit diagram label editor with English and
  Traditional Chinese interfaces, light and dark UI themes, and a light map
  paper in both themes.
- Reproducible plain-text move-list export for station names, station codes,
  angle chains, leaders, layout blocks, proposal boxes, and traced lines.
- Fictional 19-station demo network generated from source.
- Non-executing reference parser and a demo redraw path showing how a generator
  consumes name, code, and angle overrides.
- Keyboard focus for station names, with arrow-key nudging through the same
  selection and snap path used by pointer interaction.
- Content Security Policy and defensive SVG active-content removal.
- Static contract audit and 23 headless Chrome integration checks in CI.

### Known limitations

- The editor intentionally exports data rather than rewriting SVG.
- The reference demo generator applies the three universal station-label
  sections; project-specific layout sections require integration in the user's
  own generator.
- Selection is one object at a time. Collision checks are quadratic and undo
  stores full snapshots, so very large diagrams may need project-specific
  performance work.

[0.1.0]: https://github.com/aliceeeileaf19/transit-label-tuner/releases/tag/v0.1.0
