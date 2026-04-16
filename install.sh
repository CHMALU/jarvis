#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$HOME/.config/systemd/user"

echo "=== Jarvis Install ==="

echo "[1/4] Installing Python dependencies..."
python3 -m venv "$SCRIPT_DIR/.venv"
"$SCRIPT_DIR/.venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"

echo "[2/4] Setting up systemd user service..."
mkdir -p "$SERVICE_DIR"
cp "$SCRIPT_DIR/jarvis.service" "$SERVICE_DIR/jarvis.service"
systemctl --user daemon-reload

echo "[3/4] Enabling and starting Jarvis..."
systemctl --user enable --now jarvis

echo "[4/4] Status:"
systemctl --user status jarvis --no-pager

echo ""
echo "Done! Jarvis is running."
echo "  Logs:    journalctl --user -u jarvis -f"
echo "  Stop:    systemctl --user stop jarvis"
echo "  Disable: ./uninstall.sh"
