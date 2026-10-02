# Contributing

Thank you for improving auto-subtitle. This project is a macOS / Apple Silicon
demo, so changes should preserve its small, local-first scope.

## Before changing code

1. Read [AGENTS.md](AGENTS.md) for repository rules and the validation matrix.
2. Read [docs/design.md](docs/design.md) for pipeline contracts and current
   limitations.
3. Run `bin/doctor` and `tests/test_make_srt.sh` from the repository root.

## Pull-request expectations

- Keep each change focused and explain the user-visible impact.
- Include the validation commands and their results.
- Update the README or design document when commands, dependencies, data
  formats, platforms, or limitations change.
- Do not commit credentials, models, caches, generated subtitle files, or
  media beyond the repository's explicitly tracked demo fixture.

The optional `tests/test_smoke.sh` runs FFmpeg and local Whisper; it may
download a model. Run it only with appropriate local prerequisites and
authorized media.
