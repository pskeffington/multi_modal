#!/bin/sh
set -eu

APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
APP_SCRIPT="$APP_DIR/scripts/gpu_model_optimizer.py"
BIN_DIR=${XDG_BIN_HOME:-"$HOME/.local/bin"}
DATA_DIR=${XDG_DATA_HOME:-"$HOME/.local/share"}
APP_LAUNCHER="$DATA_DIR/applications/multi-modal-gpu-optimizer.desktop"
EXECUTABLE="$BIN_DIR/multi-modal-gpu-optimize"

escape_desktop_arg() {
	printf '%s' "$1" | sed 's/[\\`"$]/\\&/g'
}

ICON_DIR="$DATA_DIR/icons/hicolor/scalable/apps"
mkdir -p "$BIN_DIR" "$DATA_DIR/applications" "$ICON_DIR"
cp "$APP_DIR/data/icons/hicolor/scalable/apps/multi-modal-gpu-optimizer.svg" "$ICON_DIR/"
APP_SCRIPT_ESC=$(escape_desktop_arg "$APP_SCRIPT")
cat > "$EXECUTABLE" <<EOF
#!/bin/sh
exec /usr/bin/env python3 "$APP_SCRIPT_ESC" "\$@"
EOF
chmod 0755 "$EXECUTABLE"

EXEC_ESC=$(escape_desktop_arg "$EXECUTABLE")
write_launcher() {
	launcher_path=$1
	cat > "$launcher_path" <<EOF
[Desktop Entry]
Type=Application
Name=Multi Modal GPU Optimizer
Comment=Benchmark GPU-only local model settings with llama.cpp
TryExec="$EXEC_ESC"
Exec="$EXEC_ESC"
Icon=multi-modal-gpu-optimizer
Terminal=true
Categories=Utility;
StartupNotify=false
EOF
	chmod 0755 "$launcher_path"
}

write_launcher "$APP_LAUNCHER"
if command -v xdg-user-dir >/dev/null 2>&1; then
	DESKTOP_DIR=$(xdg-user-dir DESKTOP 2>/dev/null || true)
else
	DESKTOP_DIR="$HOME/Desktop"
fi
if [ -z "$DESKTOP_DIR" ]; then DESKTOP_DIR="$HOME/Desktop"; fi
mkdir -p "$DESKTOP_DIR"
DESKTOP_ICON="$DESKTOP_DIR/Multi Modal GPU Optimizer.desktop"
write_launcher "$DESKTOP_ICON"
if command -v gio >/dev/null 2>&1; then
	gio set "$DESKTOP_ICON" metadata::trusted true >/dev/null 2>&1 || true
fi

printf 'Installed executable: %s\n' "$EXECUTABLE"
printf 'Application menu entry: %s\n' "$APP_LAUNCHER"
printf 'Desktop icon: %s\n' "$DESKTOP_ICON"
