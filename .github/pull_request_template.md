## What this changes

<!-- One or two sentences. Link the issue if there is one. -->

## Why

<!-- The reason, not the diff. If it fixes a bug, what was the failure? -->

## Checks

- [ ] `python3 tools/selftest.py` passes (17 checks)
- [ ] If the demo network changed, it was regenerated with
      `python3 tools/make_demo_map.py` rather than hand-edited
- [ ] If an interaction was added, it has a `window.*` hook that runs the same
      snap and guard path as the mouse
- [ ] If a user-visible string was added, it goes through `t()` / `data-i18n`
      and exists in both `en` and `zh`
- [ ] If a theme-dependent value was added, it is a custom property declared
      in both theme blocks, not a raw colour in a rule

## Screenshots

<!-- For anything visual, both themes please. -->
