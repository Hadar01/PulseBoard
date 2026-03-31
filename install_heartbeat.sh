#!/usr/bin/env bash
# ============================================================
# PulseBoard-RAG — macOS LaunchAgent Installer
# ============================================================
# What this does:
#   1. Detects your Python and project directory
#   2. Writes the correct paths into the LaunchAgent plist
#   3. Copies the plist to ~/Library/LaunchAgents/
#   4. Loads it so the heartbeat scheduler starts immediately
#      and restarts automatically on every login
#
# Usage:
#   chmod +x install_heartbeat.sh
#   ./install_heartbeat.sh
#
# To uninstall:
#   launchctl unload ~/Library/LaunchAgents/com.pulseboard.heartbeat.plist
#   rm ~/Library/LaunchAgents/com.pulseboard.heartbeat.plist
# ============================================================

set -euo pipefail

PLIST_NAME="com.pulseboard.heartbeat.plist"
AGENTS_DIR="$HOME/Library/LaunchAgents"
TARGET="$AGENTS_DIR/$PLIST_NAME"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Detect Python ─────────────────────────────────────────────
echo "🔍 Detecting Python interpreter..."

# Prefer the Python that has pulseboard installed (i.e. the one in the venv)
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="$(command -v python3)"
else
    echo "❌  python3 not found.  Install Python 3.10+ and try again."
    exit 1
fi

echo "   Using: $PYTHON ($($PYTHON --version))"

# ── Validate project dir ──────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/scheduler.py" ]; then
    echo "❌  scheduler.py not found in $SCRIPT_DIR"
    echo "   Run this script from the PulseBoard-RAG project root."
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "⚠️   No .env file found."
    echo "   Run  pulseboard-config  first, then re-run this installer."
    read -p "   Continue anyway? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || exit 1
fi

# ── Create logs dir ───────────────────────────────────────────
mkdir -p "$SCRIPT_DIR/logs"

# ── Stamp plist with actual paths ────────────────────────────
echo "📝 Writing LaunchAgent plist..."
mkdir -p "$AGENTS_DIR"

sed \
    -e "s|PULSEBOARD_DIR|$SCRIPT_DIR|g" \
    -e "s|/usr/local/bin/python3|$PYTHON|g" \
    "$SCRIPT_DIR/$PLIST_NAME" > "$TARGET"

echo "   Written to: $TARGET"

# ── Unload previous version if running ───────────────────────
if launchctl list | grep -q "com.pulseboard.heartbeat" 2>/dev/null; then
    echo "🔄 Unloading previous version..."
    launchctl unload "$TARGET" 2>/dev/null || true
fi

# ── Load and start ────────────────────────────────────────────
echo "🚀 Loading heartbeat scheduler..."
launchctl load "$TARGET"

echo ""
echo "✅  PulseBoard heartbeat installed and running!"
echo ""
echo "   • Logs:      $SCRIPT_DIR/logs/heartbeat.log"
echo "   • Error log: $SCRIPT_DIR/logs/heartbeat-error.log"
echo ""
echo "   To check status:   launchctl list | grep pulseboard"
echo "   To stop:           launchctl unload $TARGET"
echo "   To view logs:      tail -f $SCRIPT_DIR/logs/heartbeat.log"
echo ""
