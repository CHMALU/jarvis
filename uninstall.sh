#!/usr/bin/env bash
set -e

echo "=== Jarvis Uninstall ==="

systemctl --user disable --now jarvis 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/jarvis.service"
systemctl --user daemon-reload

echo "Jarvis removed."
