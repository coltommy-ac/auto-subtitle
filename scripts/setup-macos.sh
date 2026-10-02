#!/bin/bash
# Prepare the local development/runtime environment for auto-subtitle.
# This script never creates credentials or downloads a Whisper model.

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
project_root=$(dirname "$script_dir")
install_homebrew=0

usage() {
    cat <<'EOF'
Usage: scripts/setup-macos.sh [--install-homebrew]

Installs missing FFmpeg and Python through Homebrew, creates .venv, installs
mlx-whisper, then runs doctor and the offline fixture test.

--install-homebrew  When Homebrew is absent, download and run its official
                    installer. It may ask for administrator authentication.
EOF
}

case "${1:-}" in
    "") ;;
    --install-homebrew) install_homebrew=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
esac

if [ "$(uname -s)" != "Darwin" ]; then
    echo "error: setup is supported only on macOS" >&2
    exit 1
fi

if [ "$(uname -m)" != "arm64" ]; then
    echo "error: the current MLX transcription adapter requires Apple Silicon (arm64)" >&2
    exit 1
fi

cd "$project_root"

echo "==> Checking the current environment"
"$project_root/bin/doctor" || true

if ! command -v brew >/dev/null 2>&1; then
    if [ "$install_homebrew" -ne 1 ]; then
        cat >&2 <<'EOF'

error: Homebrew is required to install FFmpeg automatically, but it is not installed.
macOS does not include Homebrew or FFmpeg by default.

Install Homebrew yourself from https://brew.sh, then rerun this script; or run:
  scripts/setup-macos.sh --install-homebrew

The --install-homebrew option downloads and executes Homebrew's official
installer and may request administrator authentication.
EOF
        exit 1
    fi

    if ! command -v curl >/dev/null 2>&1; then
        echo "error: curl is required to download the official Homebrew installer" >&2
        exit 1
    fi

    echo "==> Installing Homebrew using its official installer"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if [ -x /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
fi

if ! command -v brew >/dev/null 2>&1; then
    echo "error: Homebrew installation completed but brew is not on PATH; open a new terminal and rerun this script" >&2
    exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
    echo "==> Installing FFmpeg"
    brew install ffmpeg
fi

python_cmd=""
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    python_cmd=$(command -v python3)
else
    echo "==> Installing Python 3 through Homebrew"
    brew install python
    python_cmd=$(command -v python3)
fi

if [ ! -x .venv/bin/python ]; then
    echo "==> Creating .venv"
    "$python_cmd" -m venv .venv
fi

echo "==> Installing Python dependencies in .venv"
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo "==> Verifying the configured environment"
(
    source .venv/bin/activate
    "$project_root/bin/doctor"
)

echo "==> Running the offline SRT fixture"
"$project_root/tests/test_make_srt.sh"

cat <<'EOF'

Setup complete.
For this terminal, activate the environment before running the project:
  source .venv/bin/activate

The first transcription downloads the selected Whisper model. For a small
first run, use: WHISPER_MODEL=tiny bin/autosub /path/to/video.mp4 en en
EOF
