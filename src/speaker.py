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

import aiohttp
import sounddevice as sd
import soundfile as sf

from text_utils import split_for_speech

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

    async def warmup(self):
        """Warm up TTS stack with a tiny synthesis to reduce first-turn latency."""
        try:
            audio_path = await self._synthesize("Ready.")
            try:
                audio_path.unlink()
            except Exception:
                pass
            log.info("TTS warmup complete")
        except Exception as e:
            log.warning("TTS warmup failed: %s", e)

    async def say(self, text: str):
        """Synthesize text and play it through the speaker in short speech chunks."""
        text = text.strip()
        if not text:
            return
        try:
            chunks = split_for_speech(text)
            if not chunks:
                return
            for chunk in chunks:
                audio_path = await self._synthesize(chunk)
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
        """Synthesize speech using the configured provider."""
        provider = (self.config.tts_provider or "edge").strip().lower()

        if provider == "elevenlabs":
            if not self.config.elevenlabs_api_key or not self.config.elevenlabs_voice_id:
                raise RuntimeError("ElevenLabs selected but ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID not set")
            return await self._synthesize_elevenlabs(text)

        if provider == "pyttsx3":
            return await self._synthesize_pyttsx3(text)

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

    async def _synthesize_elevenlabs(self, text: str) -> Path:
        """Synthesize speech using ElevenLabs REST API."""
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.config.elevenlabs_voice_id}"
        payload = {
            "text": text,
            "model_id": self.config.elevenlabs_model_id,
        }
        headers = {
            "xi-api-key": self.config.elevenlabs_api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"ElevenLabs HTTP {resp.status}: {body[:200]}")
                audio = await resp.read()
                with open(tmp.name, "wb") as f:
                    f.write(audio)
        return Path(tmp.name)

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
