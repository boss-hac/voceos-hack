#!/bin/bash

DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$DIR"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    playwright install chromium
else
    source .venv/bin/activate
fi

python3 browser_control.py
