#!/bin/bash
# Optional end-to-end test. It intentionally is not called by setup or the
# default fixture because mlx-whisper may download the tiny model on first use.

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
media_file="$repo_root/samples/sample.mov"

usage() {
    cat <<'EOF'
Usage: tests/test_smoke.sh [--media /absolute/or/relative/path]

Runs FFmpeg, mlx-whisper's tiny model, and SRT generation against the first
five seconds of authorized local media. The default is the included
samples/sample.mov; no other media is added to Git by this test.
EOF
}

case "${1:-}" in
    "") ;;
    --media)
        [ "$#" -eq 2 ] || { usage >&2; exit 2; }
        media_file="$2"
        ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
esac

if [ ! -f "$media_file" ]; then
    echo "error: local smoke-test media not found: $media_file" >&2
    echo "Provide authorized media with: tests/test_smoke.sh --media /path/to/video" >&2
    exit 2
fi

for command_name in ffmpeg ffprobe mlx_whisper; do
    command -v "$command_name" >/dev/null 2>&1 || {
        echo "error: $command_name is required; activate .venv and run bin/doctor" >&2
        exit 1
    }
done

work_dir=$(mktemp -d)
cache_name="autosub-smoke-$$"
smoke_media="$work_dir/$cache_name.mkv"
cache_dir="$repo_root/cache/$cache_name"
trap 'rm -rf "$work_dir" "$cache_dir"' EXIT

echo "Preparing a five-second temporary media clip..."
ffmpeg -hide_banner -loglevel error -y -i "$media_file" -t 5 -map 0 -c copy "$smoke_media"

echo "Running the full pipeline with WHISPER_MODEL=tiny..."
WHISPER_MODEL=tiny "$repo_root/bin/autosub" "$smoke_media" zh zh

smoke_srt="$work_dir/$cache_name.zh.srt"
if [ ! -s "$smoke_srt" ]; then
    echo "error: smoke test did not produce a non-empty SRT: $smoke_srt" >&2
    exit 1
fi

echo "end-to-end smoke test passed"
