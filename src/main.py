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


async def handle_one_turn(config, listener, wake, relay, speaker):
    if config.test_mode:
        log.info("Test mode enabled — press Enter to record, Ctrl+C to quit")
        await asyncio.to_thread(input)
        detected = True
    else:
        try:
            detected = await asyncio.wait_for(wake.wait_for_wake_word(), timeout=1.0)
        except asyncio.TimeoutError:
            return

    if not detected:
        return

    log.info("Wake/trigger detected — recording utterance")
    await speaker.play_chime()

    audio_path = await listener.record_utterance()
    if audio_path is None:
        log.warning("No speech captured")
        await speaker.play_error_chime()
        return

    text = await listener.transcribe(audio_path)
    if not text or len(text.strip()) < 2:
        log.info("Empty transcription, ignoring")
        await speaker.play_error_chime()
        return

    log.info("Heard: %r", text)

    try:
        response = await relay.send(text)
    except Exception as e:
        log.error("Relay error: %s", e)
        await speaker.say("Sorry, I couldn't reach my brain right now.")
        return

    if not response:
        await speaker.say("I didn't get a response. Try again.")
        return

    log.info("Response: %r", response[:120])
    await speaker.say(response)


async def run():
    config = Config.load()
    log.info("Starting hal-speaker (device: %s)", config.device_name)
    log.info(
        "Audio config: input_device=%s output_device=%s sample_rate=%s test_mode=%s",
        config.input_device,
        config.output_device,
        config.sample_rate,
        config.test_mode,
    )

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

    current_turn: asyncio.Task | None = None

    log.info("Preloading Whisper model...")
    await listener.preload()
    await speaker.warmup()
    await speaker.say_startup()

    if config.test_mode:
        log.info("Ready in push-to-talk test mode")
    else:
        log.info("Listening for wake word: '%s'", config.wake_word)

    while not stop.is_set():
        try:
            current_turn = asyncio.create_task(handle_one_turn(config, listener, wake, relay, speaker))
            await current_turn
            current_turn = None
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error("Turn failed: %s", e)
            await asyncio.sleep(1)

    if current_turn and not current_turn.done():
        current_turn.cancel()
        try:
            await asyncio.wait_for(current_turn, timeout=1.0)
        except Exception:
            pass

    await relay.close()
    log.info("hal-speaker stopped")


if __name__ == "__main__":
    Path("logs").mkdir(exist_ok=True)
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("Interrupted by user, exiting cleanly")
