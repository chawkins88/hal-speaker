"""
TTS and audio playback.

Uses edge-tts (Microsoft neural TTS, free, no API key) for speech synthesis.
Falls back to pyttsx3 if edge-tts is unavailable offline.
Plays audio through the system speaker (or specified output device).
"""

import asyncio
import logging
import tempfile
from pathlib import Path

import sounddevice as sd
import soundfile as sf

log = logging.getLogger("speaker")

STARTUP_MESSAGES = [
    "Hal is ready.",
    "I'm listening.",
    "Online and ready.",
]


class Speaker:
    def __init__(self, config):
        self.config = config
        self._startup_idx = 0

    async def say(self, text: str):
        """Synthesize text and play it through the speaker."""
        text = text.strip()
        if not text:
            return
        try:
            audio_path = await self._synthesize(text)
            await self._play(audio_path)
        except Exception as e:
            log.error("TTS error: %s", e)

    async def say_startup(self):
        msgs = STARTUP_MESSAGES
        msg = msgs[self._startup_idx % len(msgs)]
        self._startup_idx += 1
        await self.say(msg)

    async def play_chime(self):
        chime_path = Path(__file__).parent.parent / self.config.chime_wake
        if chime_path.exists():
            await self._play(chime_path)
        else:
            # Synthesize a short tone via TTS if no chime file
            log.debug("No chime file at %s, skipping", chime_path)

    async def play_error_chime(self):
        chime_path = Path(__file__).parent.parent / self.config.chime_error
        if chime_path.exists():
            await self._play(chime_path)

    async def _synthesize(self, text: str) -> Path:
        """Use edge-tts to synthesize speech. Returns path to audio file."""
        try:
            import edge_tts

            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            communicate = edge_tts.Communicate(
                text,
                voice=self.config.tts_voice,
                rate=self.config.tts_rate,
                pitch=self.config.tts_pitch,
            )
            await communicate.save(tmp.name)
            return Path(tmp.name)

        except ImportError:
            log.warning("edge-tts not available, falling back to pyttsx3")
            return await self._synthesize_pyttsx3(text)

    async def _synthesize_pyttsx3(self, text: str) -> Path:
        """Offline TTS fallback using pyttsx3."""
        import pyttsx3

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        loop = asyncio.get_event_loop()

        def _run():
            engine = pyttsx3.init()
            engine.save_to_file(text, tmp.name)
            engine.runAndWait()

        await loop.run_in_executor(None, _run)
        return Path(tmp.name)

    async def _play(self, audio_path: Path):
        """Play an audio file through the output device."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._play_blocking, audio_path)

    def _play_blocking(self, audio_path: Path):
        try:
            data, samplerate = sf.read(str(audio_path))
            sd.play(data, samplerate, device=self.config.output_device)
            sd.wait()
        except Exception as e:
            log.error("Playback error for %s: %s", audio_path, e)
        finally:
            try:
                audio_path.unlink()
            except Exception:
                pass
