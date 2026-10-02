# auto-subtitle

A small macOS / Apple Silicon demo that generates an SRT subtitle file from a local media file.

The pipeline extracts mono audio with FFmpeg, transcribes it locally with
[mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper),
and converts timestamped recognition segments to SRT. It can optionally
translate the generated subtitles through DeepL or Baidu Translate.

> This is a learning/demo project, not a production-ready subtitle service.
> Only process media you own or are authorized to process.

## What is included

- `bin/autosub`: pipeline entry point
- `bin/extract-meta` and `bin/extract-audio`: FFmpeg/ffprobe media preparation
- `bin/stt_engine`: mlx-whisper adapter
- `bin/make-srt.py`: timestamped JSON to SRT converter
- `bin/translate.py`: optional DeepL/Baidu translation adapter
- `samples/PMQ.flv`: a short demo video for the opt-in smoke test
- `tests/`: a synthetic, no-media regression fixture for SRT generation

No trained model, API credential, cache, virtual environment, or third-party
binary is included in this repository. Apart from `samples/PMQ.flv`, do not
commit media to the repository.

## Requirements

- macOS on Apple Silicon (required by the current MLX transcription adapter)
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) (`brew install ffmpeg`)
- Python packages listed in `requirements.txt` (installed by setup)

The direct runtime dependency is pinned in `requirements.txt` so new installs
use the same verified `mlx-whisper` CLI version rather than whichever version
is newest on PyPI.

The first transcription downloads the selected Whisper model. The default is
`large`; use a smaller model for a quick demo, for example:

```bash
export WHISPER_MODEL=tiny
```

Check the prerequisites before running a transcription:

```bash
bin/doctor
```

For an optional translation provider, also check that its credential is
available without revealing its value:

```bash
bin/doctor --engine deepl
```

## Quick start

```bash
git clone https://github.com/coltommy-ac/auto-subtitle.git
cd auto-subtitle

# Install FFmpeg (via Homebrew), create .venv, install mlx-whisper,
# then run doctor and the offline fixture test.
scripts/setup-macos.sh
source .venv/bin/activate

# Generate source-language subtitles only
WHISPER_MODEL=tiny bin/autosub /path/to/video.mp4 en en

# Generate Japanese subtitles and translate them to Chinese with DeepL
WHISPER_MODEL=tiny bin/autosub /path/to/video.mp4 ja zh --engine deepl
```

Homebrew is not part of macOS. If it is not installed, either install it from
[brew.sh](https://brew.sh) and rerun setup, or explicitly allow setup to run
Homebrew's official installer:

```bash
scripts/setup-macos.sh --install-homebrew
```

The generated file is placed next to the input media as
`<video-name>.<language>.srt`; working files are placed under `cache/`.

## Optional translation credentials

Create `~/.autosub_credentials` locally (never commit it):

```ini
DEEPL_APIKEY=your_key
# Or use Baidu Translate:
BAIDU_APPID=your_app_id
BAIDU_APPKEY=your_app_key
```

Alternatively, set the same variables in your shell environment. Translation
requests are sent to the selected provider; transcription itself runs locally.
See [`docs/translation-credentials.example`](docs/translation-credentials.example)
for the provider-specific setup and security boundary.

## Verify the included fixture

```bash
tests/test_make_srt.sh
```

It uses a synthetic recognition result and does not call a model or network.

## Optional end-to-end smoke test

The smoke test is deliberately separate from the default fixture: it runs
FFmpeg and the `tiny` Whisper model, which may download that model on first
use. It creates a five-second temporary copy of local media and removes all
outputs after the check.

`samples/PMQ.flv` is the included default input. It is used only when you
explicitly run this test:

```bash
tests/test_smoke.sh
```

To use another authorized local file:

```bash
tests/test_smoke.sh --media /path/to/video.mp4
```

All executable entry points can be invoked from any working directory; their
project-relative helpers and cache location are resolved from the script path.

## Limitations

- The current recognition adapter is Apple-Silicon-specific.
- Accuracy, latency, and model-download size depend on the selected Whisper
  model and source audio.
- Subtitle segmentation is intentionally simple and should be reviewed before
  publication or professional use.
- This project does not ship a media sample or guarantee rights for user media.

## License

[MIT](LICENSE). Copyright (c) 2026 guoxr.
