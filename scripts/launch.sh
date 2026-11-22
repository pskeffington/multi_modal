#!/bin/sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export PYTHONPATH="$APP_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m multi_modal.app "$@"
