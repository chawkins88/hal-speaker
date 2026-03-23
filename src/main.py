"""
hal-speaker: Voice relay service for Hal AI assistant.

Pipeline:
  mic → wake word detection → STT (Whisper) → relay to Hal → TTS → speaker

Hardware: Mini PC + ReSpeaker far-field mic array + speakers
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from config import Config
from wake import WakeWordDetector
from listener import Listener
from relay import HalRelay
from speaker import Speaker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path(__file__).parent.parent / "logs" / "hal-speaker.log"),
    ],
)
log = logging.getLogger("hal-speaker")


async def run():
    config = Config.load()
    log.info("Starting hal-speaker (device: %s)", config.device_name)

    relay = HalRelay(config)
    speaker = Speaker(config)
    listener = Listener(config)
    wake = WakeWordDetector(config)

    # Graceful shutdown
    stop = asyncio.Event()

    def _shutdown(sig, frame):
        log.info("Shutting down (%s)", sig)
        stop.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    await speaker.say_startup()

    log.info("Listening for wake word: '%s'", config.wake_word)

    while not stop.is_set():
        try:
            # Block until wake word detected
            detected = await asyncio.wait_for(wake.wait_for_wake_word(), timeout=1.0)
        except asyncio.TimeoutError:
            continue

        if not detected:
            continue

        log.info("Wake word detected — recording utterance")
        await speaker.play_chime()

        # Record utterance until silence
        audio_path = await listener.record_utterance()
        if audio_path is None:
            log.warning("No speech captured")
            await speaker.play_error_chime()
            continue

        # Transcribe
        text = await listener.transcribe(audio_path)
        if not text or len(text.strip()) < 2:
            log.info("Empty transcription, ignoring")
            await speaker.play_error_chime()
            continue

        log.info("Heard: %r", text)

        # Relay to Hal
        try:
            response = await relay.send(text)
        except Exception as e:
            log.error("Relay error: %s", e)
            await speaker.say("Sorry, I couldn't reach my brain right now.")
            continue

        if not response:
            await speaker.say("I didn't get a response. Try again.")
            continue

        log.info("Response: %r", response[:120])

        # Speak the response
        await speaker.say(response)

    log.info("hal-speaker stopped")


if __name__ == "__main__":
    Path("logs").mkdir(exist_ok=True)
    asyncio.run(run())
