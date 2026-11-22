#!/bin/sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
APP_DIR_ESCAPED=$(printf '%s' "$APP_DIR" | sed 's/\\/\\\\/g; s/"/\\"/g')
DESKTOP_DIR=${XDG_DATA_HOME:-"$HOME/.local/share"}/applications
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/multi-modal-router.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Multi Modal Task Router
Comment=Queue tasks to local Qwen and GLM models
Exec=/bin/sh "$APP_DIR_ESCAPED/scripts/launch.sh"
Terminal=false
Categories=Development;Utility;
StartupNotify=true
EOF
chmod 0644 "$DESKTOP_DIR/multi-modal-router.desktop"
printf 'Installed launcher: %s\n' "$DESKTOP_DIR/multi-modal-router.desktop"
