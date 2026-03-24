# hal-speaker

Voice relay service for the Hal AI assistant. Runs on a dedicated mini PC with
a ReSpeaker far-field mic array and speakers.

**Pipeline:** mic → wake word → STT → relay to Hal → TTS → speaker

Hal is the brain. This device is just ears and a mouth.

## Hardware

- Mini PC (x86 Linux)
- ReSpeaker USB far-field mic array
- Speakers (any — USB, 3.5mm, HDMI)

## Stack

| Layer | Library | Notes |
|---|---|---|
| Wake word | openWakeWord | Free, local, supports custom models |
| STT | faster-whisper | Local Whisper inference, fast on CPU |
| Relay | aiohttp | HTTP POST to OpenClaw gateway |
| TTS | edge-tts | Microsoft neural voices, free |
| Audio I/O | sounddevice | PortAudio wrapper |

## Setup

```bash
git clone https://github.com/chawkins88/hal-speaker
cd hal-speaker
bash scripts/setup.sh
```

Then edit `.env` with your settings.

## Configuration

Key settings in `.env`:

```
OPENCLAW_URL=http://<hal-vm-ip>:18789
OPENCLAW_SESSION_KEY=agent:main:voice:hal-speaker
OPENCLAW_AUTH_TOKEN=<voice-relay-auth-token>
TTS_VOICE=en-US-GuyNeural
WHISPER_MODEL=base.en
SAMPLE_RATE=16000
```

Find your audio device indices:
```bash
source .venv/bin/activate
python3 -m sounddevice
```

If startup fails with `Invalid sample rate`, try:
- `SAMPLE_RATE=44100`
- `SAMPLE_RATE=48000`
- or leave `INPUT_DEVICE` / `OUTPUT_DEVICE` blank to use the system default audio path

If the selected input device fails to open, `hal-speaker` now retries automatically with the system default input device and logs the failure clearly.

If wake-word startup fails with NumPy/tflite errors, make sure the venv has:
```bash
pip install 'numpy<2'
```

For easier first testing, enable push-to-talk mode:
```bash
TEST_MODE=true
```
Then run the app and press **Enter** to record a turn instead of using the wake word.

## Running

```bash
source .venv/bin/activate
python3 src/main.py
```

Or as a systemd service:
```bash
sudo cp systemd/hal-speaker.service /etc/systemd/system/
sudo systemctl enable --now hal-speaker
```

## Wake Word

The default wake word is `hey_hal`. A custom openWakeWord model (`models/hey_hal.onnx`)
is needed for production. Until then, it falls back to `hey_jarvis` for testing.

To train a custom model: https://github.com/dscripka/openWakeWord#training-new-models

## Architecture

```
┌─────────────────────────────────────────┐
│             mini PC                     │
│                                         │
│  ReSpeaker ──► wake.py                  │
│                  │                      │
│               listener.py (Whisper)     │
│                  │                      │
│               relay.py ──► OpenClaw     │
│                  │         Gateway      │
│               speaker.py (edge-tts)     │
│                  │                      │
│             Speakers ◄──────────────────┘
└─────────────────────────────────────────┘
```
