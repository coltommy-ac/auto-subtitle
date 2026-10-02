#!/bin/bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
fixture_dir=$(mktemp -d)
trap 'rm -rf "$fixture_dir"' EXIT

cp "$repo_root/tests/fixtures/index" "$fixture_dir/index"
cp "$repo_root/tests/fixtures/clip_0.en.txt" "$fixture_dir/clip_0.en.txt"
python3 "$repo_root/bin/make-srt.py" -d "$fixture_dir" -l en >/dev/null
diff -u "$repo_root/tests/fixtures/expected.en.srt" "$fixture_dir/output.en.srt"
echo "make-srt fixture passed"
