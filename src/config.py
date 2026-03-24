"""Configuration loader for hal-speaker."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


@dataclass
class Config:
    # Device identity
    device_name: str = "hal-speaker"

    # Wake word / test mode
    wake_word: str = "hey_hal"
    wake_word_threshold: float = 0.5
    test_mode: bool = False          # if true, bypass wake word and use Enter-to-talk

    # Audio hardware
    # Run `python3 -m sounddevice` to list device indices
    input_device: int | None = None   # None = system default (ReSpeaker usually auto-detected)
    output_device: int | None = None  # None = system default
    sample_rate: int = 16000          # configurable; some USB mics want 44100 or 48000
    channels: int = 1

    # Recording
    silence_threshold: float = 0.01   # RMS below this = silence
    silence_duration: float = 1.5     # seconds of silence to end utterance
    max_utterance_duration: float = 30.0

    # STT
    whisper_model: str = "base.en"    # tiny.en / base.en / small.en
    whisper_device: str = "cpu"       # cpu or cuda

    # Relay (OpenClaw gateway)
    openclaw_url: str = "http://localhost:9999"
    openclaw_channel: str = "voice"
    openclaw_session_key: str = ""    # Set in .env: OPENCLAW_SESSION_KEY
    relay_timeout: float = 30.0

    # TTS
    tts_voice: str = "en-US-GuyNeural"   # or en-US-JennyNeural, etc.
    tts_rate: str = "+0%"
    tts_pitch: str = "+0Hz"

    # Chime audio files (relative to project root)
    chime_wake: str = "assets/chime_wake.wav"
    chime_error: str = "assets/chime_error.wav"

    @classmethod
    def load(cls) -> "Config":
        return cls(
            device_name=os.getenv("DEVICE_NAME", "hal-speaker"),
            wake_word=os.getenv("WAKE_WORD", "hey_hal"),
            wake_word_threshold=float(os.getenv("WAKE_WORD_THRESHOLD", "0.5")),
            test_mode=os.getenv("TEST_MODE", "false").strip().lower() in {"1", "true", "yes", "on"},
            input_device=_int_or_none(os.getenv("INPUT_DEVICE")),
            output_device=_int_or_none(os.getenv("OUTPUT_DEVICE")),
            sample_rate=int(os.getenv("SAMPLE_RATE", "16000")),
            whisper_model=os.getenv("WHISPER_MODEL", "base.en"),
            whisper_device=os.getenv("WHISPER_DEVICE", "cpu"),
            openclaw_url=os.getenv("OPENCLAW_URL", "http://localhost:9999"),
            openclaw_channel=os.getenv("OPENCLAW_CHANNEL", "voice"),
            openclaw_session_key=os.getenv("OPENCLAW_SESSION_KEY", ""),
            relay_timeout=float(os.getenv("RELAY_TIMEOUT", "30")),
            tts_voice=os.getenv("TTS_VOICE", "en-US-GuyNeural"),
            tts_rate=os.getenv("TTS_RATE", "+0%"),
            tts_pitch=os.getenv("TTS_PITCH", "+0Hz"),
        )


def _int_or_none(val: str | None) -> int | None:
    if val is None or val.strip() == "":
        return None
    return int(val)
