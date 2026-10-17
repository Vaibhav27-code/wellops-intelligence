#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ASSET_INTELLIGENCE_DATASET="$repo_root/data/raw/flytbase-ahc-swe-asset-intelligence-dataset"
export ASSET_INTELLIGENCE_DB="$repo_root/data/demo.db"
export LLM_CACHE_PATH="$repo_root/data/demo_llm_cache.db"
python_exe="$repo_root/.venv/bin/python"
if [[ ! -x "$python_exe" ]]; then python_exe="python"; fi
"$python_exe" "$repo_root/scripts/demo_reset.py"
