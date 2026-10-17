#!/bin/bash
# Bootstrap, build, and run the Discord Browser VM application

# Exit on error
set -e

# Get current script path
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "============================================="
echo "🛰️  Initializing NexusVM Browser Application"
echo "============================================="

# 1. Setup python virtual environment
if [ ! -d "venv" ]; then
    echo "[*] Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "[*] Activating virtual environment..."
source venv/bin/activate

echo "[*] Installing backend dependencies..."
pip install -r backend/requirements.txt

# Ensure playwright is installed
echo "[*] Skipping Playwright automatic browser installation (using system Chromium)..."
# playwright install chromium

# 2. Build React frontend
echo "[*] Setting up Vite frontend..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "[*] Installing Node dependencies..."
    npm install
fi

echo "[*] Building frontend for production..."
npm run build
cd "$DIR"

echo "============================================="
echo "🚀 Starting Browser VM and Discord Bot"
echo "============================================="

# Trap ctrl-c and stop services
trap "echo -e '\nStopping services...'; kill 0" SIGINT SIGTERM

# Run FastAPI backend
python3 backend/main.py &

# Run Discord bot
python3 bot.py &

# Keep script running
wait
