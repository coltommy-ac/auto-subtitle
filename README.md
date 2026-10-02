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
- `tests/`: a synthetic, no-media regression fixture for SRT generation

No media, trained model, API credential, cache, virtual environment, or
third-party binary is included in this repository.

## Requirements

- macOS on Apple Silicon (required by the current MLX transcription adapter)
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) (`brew install ffmpeg`)
- `mlx-whisper` (`python3 -m pip install mlx-whisper`)

The first transcription downloads the selected Whisper model. The default is
`large`; use a smaller model for a quick demo, for example:

```bash
export WHISPER_MODEL=tiny
```

## Quick start

```bash
git clone https://github.com/coltommy-ac/auto-subtitle.git
cd auto-subtitle

# Generate source-language subtitles only
WHISPER_MODEL=tiny bin/autosub /path/to/video.mp4 en en

# Generate Japanese subtitles and translate them to Chinese with DeepL
WHISPER_MODEL=tiny bin/autosub /path/to/video.mp4 ja zh --engine deepl
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

## Verify the included fixture

```bash
tests/test_make_srt.sh
```

It uses a synthetic recognition result and does not call a model or network.

## Limitations

- The current recognition adapter is Apple-Silicon-specific.
- Accuracy, latency, and model-download size depend on the selected Whisper
  model and source audio.
- Subtitle segmentation is intentionally simple and should be reviewed before
  publication or professional use.
- This project does not ship a media sample or guarantee rights for user media.

## License

[MIT](LICENSE). Copyright (c) 2026 guoxr.
