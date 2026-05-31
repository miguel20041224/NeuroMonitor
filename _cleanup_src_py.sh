#!/bin/sh
set -e
exec python3 "$(dirname "$0")/_remove_legacy_src.py"
