#!/usr/bin/env bash
# One-time setup for macOS (Terminal, from inside the project folder):   bash scripts/setup_mac.sh
set -euo pipefail

echo "== GrowthPulse setup =="
echo "Project folder: $(pwd)"
if [ ! -f "requirements.txt" ]; then
  echo "ERROR: requirements.txt not found. You are not inside the growthpulse folder."
  echo "       In Terminal run:  cd <path to the growthpulse folder>   (see README 'Open the project')"
  exit 1
fi

PY=""
for c in python3.12 python3.13 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then PY="$c"; break; fi
  fi
done
if [ -z "$PY" ]; then
  echo "ERROR: Python 3.11 or newer was not found."
  echo "       Install it:  brew install python@3.12     (Homebrew: https://brew.sh)  or download from https://www.python.org/downloads/"
  exit 1
fi
echo "Using $($PY --version) at $(command -v $PY)"

if [ ! -d ".venv" ]; then "$PY" -m venv .venv; fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
echo
echo "Setup finished. Next (every new Terminal window you must re-activate the environment first):"
echo "  source .venv/bin/activate"
echo "  python scripts/run_pipeline.py --regenerate"
echo "  streamlit run app/streamlit_app.py"
