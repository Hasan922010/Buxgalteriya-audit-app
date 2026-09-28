#!/usr/bin/env bash
# ==============================================================================
# Autonomous Antigravity Runner for Yordamchi Buxgalter AI
# ==============================================================================
set -e

echo "[Antigravity] Initializing environment..."
CONFIG_FILE=".antigravity/config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "[Antigravity] Config file not found: $CONFIG_FILE"
    exit 1
fi

echo "[Antigravity] Loading config from $CONFIG_FILE"
echo "[Antigravity] Executing Master Plan..."

cd backend
python -m pytest tests/ -v
cd ..

echo "[Antigravity] System execution and verification successful."
