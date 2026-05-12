#!/usr/bin/env bash
set -euo pipefail
python main.py validate
python main.py serve --reload
