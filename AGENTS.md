# Agent and contributor guide

## Purpose and scope

`auto-subtitle` is a macOS / Apple Silicon demo for local subtitle generation.
Treat [`docs/design.md`](docs/design.md) as the detailed, versioned design
contract. Do not claim production readiness or cross-platform support.

## Fast start

Run these commands from the repository root:

```bash
bin/doctor
tests/test_make_srt.sh
```

`bin/doctor` checks prerequisites without installing software, downloading a
model, or printing credentials. The fixture test is offline and should be run
for changes to `bin/make-srt.py` or its input/output contract.

Only run the opt-in end-to-end check when FFmpeg, `mlx-whisper`, an authorized
local media file, and a potentially downloaded `tiny` model are acceptable:

```bash
tests/test_smoke.sh [--media /path/to/video]
```

## Maintained implementation

| Area | Source of truth |
|---|---|
| Pipeline entry point | `bin/autosub` |
| Environment checks | `bin/doctor` |
| Media preparation | `bin/extract-meta`, `bin/extract-audio` |
| Local transcription | `bin/speech2text`, `bin/stt_engine` |
| SRT generation | `bin/make-srt.py` |
| Translation | `bin/translate.py` |
| Setup | `scripts/setup-macos.sh` |
| Detailed behavior and constraints | `docs/design.md` |

Local files matched by `.gitignore` are not part of the maintained codebase.
In particular, do not use `bin/*.bak`, `bin/*.php`, `bin/identify`, `tools/`,
`cache/`, `.venv/`, generated subtitles, or user media as an implementation
reference unless a task explicitly targets legacy migration.

## Change rules

1. Inspect the relevant entry point and its direct callers before editing.
2. Keep changes scoped; do not reformat or refactor unrelated scripts.
3. Preserve the current contracts: cache layout, `index` offsets, normalized
   STT JSON, SRT timestamps, and credentials outside Git.
4. Do not add model files, credentials, caches, generated audio, or unlicensed
   media to Git.
5. Update `README.md`, `README.zh-CN.md`, or `docs/design.md` when a user
   visible command, dependency, contract, supported platform, or limitation
   changes.
6. State the commands run and any checks deliberately not run in the handoff.

## Style and safety

- Match the surrounding Bash or Python style; use no new runtime dependency
  unless the task requires it.
- Prefer explicit failure messages and non-zero exits over partial success.
- Use temporary files plus rename for generated artifacts when the existing
  pipeline does so.
- Never print, commit, or copy translation credentials. Keep them in
  `~/.autosub_credentials` or the environment.
- Process only media the user is authorized to handle. Translation sends text
  to the selected external provider; transcription is local.

## Handoff checklist

- `git diff --check`
- Relevant test(s) passed, or the reason they were not run
- Documentation adjusted when behavior changed
- No generated artifacts or secrets included
