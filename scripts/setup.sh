#!/bin/bash
# hal-speaker setup script
# Run once on the mini PC after cloning the repo

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== hal-speaker setup ==="

# System deps (Ubuntu/Debian)
echo "Installing system packages..."
sudo apt-get update -q
sudo apt-get install -y \
    python3 python3-pip python3-venv \
    portaudio19-dev \
    libsndfile1 \
    ffmpeg \
    espeak-ng  # pyttsx3 fallback TTS engine

# Create venv
echo "Creating Python venv..."
python3 -m venv "$ROOT/.venv"
source "$ROOT/.venv/bin/activate"

# Install Python deps
echo "Installing Python packages..."
pip install --upgrade pip
pip install -r "$ROOT/requirements.txt"

# Download openWakeWord models
echo "Downloading openWakeWord base models..."
python3 -c "
import openwakeword
openwakeword.utils.download_models()
print('openWakeWord models downloaded')
"

# Create dirs
mkdir -p "$ROOT/logs" "$ROOT/models" "$ROOT/assets"

# Copy env template
if [ ! -f "$ROOT/.env" ]; then
    cp "$ROOT/.env.example" "$ROOT/.env"
    echo ""
    echo "*** Edit $ROOT/.env with your settings before starting ***"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env — set OPENCLAW_URL and other settings"
echo "  2. Run: python3 -m sounddevice   (to find your mic/speaker device indices)"
echo "  3. Set INPUT_DEVICE / OUTPUT_DEVICE in .env if needed"
echo "  4. Test: source .venv/bin/activate && python3 src/main.py"
echo ""
echo "For wake word: place a custom hey_hal.onnx in models/ (see README)"
echo "  or leave as-is to test with the 'hey_jarvis' placeholder"
