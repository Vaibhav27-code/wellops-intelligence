#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: scripts/test_day.sh <dataset-folder> <final-questions.json> [output-directory]" >&2
  exit 2
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"
if [[ -x "$repo_root/.venv/bin/python" ]]; then
  python_bin="$repo_root/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  python_bin="$(command -v python3)"
else
  python_bin="$(command -v python)"
fi

if [[ $# -eq 3 ]]; then
  exec "$python_bin" "$script_dir/test_day.py" "$1" "$2" --output-dir "$3"
fi
exec "$python_bin" "$script_dir/test_day.py" "$1" "$2"
