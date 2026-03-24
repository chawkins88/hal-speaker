"""
Audio recording and speech-to-text transcription.

Records from microphone until silence is detected, then transcribes
using faster-whisper (local, no API key needed).
"""

import asyncio
import logging
import tempfile
import wave
from pathlib import Path

import numpy as np
import soundfile as sf

from audio_utils import open_input_stream_with_fallback

log = logging.getLogger("listener")


class Listener:
    def __init__(self, config):
        self.config = config
        self._whisper = None

    def _load_whisper(self):
        if self._whisper is not None:
            return
        try:
            from faster_whisper import WhisperModel
            log.info("Loading Whisper model: %s on %s", self.config.whisper_model, self.config.whisper_device)
            self._whisper = WhisperModel(
                self.config.whisper_model,
                device=self.config.whisper_device,
                compute_type="int8",
            )
            log.info("Whisper model loaded")
        except ImportError:
            raise RuntimeError("faster-whisper not installed. Run: pip install faster-whisper")

    async def record_utterance(self) -> Path | None:
        """
        Record audio from mic until silence is detected.
        Returns path to a temporary WAV file, or None if nothing captured.
        """
        loop = asyncio.get_event_loop()
        audio_data = await loop.run_in_executor(None, self._record_blocking)

        if audio_data is None or len(audio_data) < self.config.sample_rate * 0.3:
            # Less than 300ms of audio — probably nothing
            return None

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(tmp.name, audio_data, self.config.sample_rate)
        return Path(tmp.name)

    def _record_blocking(self) -> np.ndarray | None:
        """Record until silence. Returns float32 audio array or None."""
        sample_rate = self.config.sample_rate
        silence_thresh = self.config.silence_threshold
        silence_dur = self.config.silence_duration
        max_dur = self.config.max_utterance_duration
        chunk_size = int(sample_rate * 0.1)  # 100ms chunks

        frames = []
        silent_chunks = 0
        silent_chunks_needed = int(silence_dur / 0.1)
        max_chunks = int(max_dur / 0.1)
        has_speech = False

        log.debug("Recording utterance (silence threshold=%.3f, silence=%.1fs)", silence_thresh, silence_dur)

        try:
            stream_ctx = open_input_stream_with_fallback(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                device=self.config.input_device,
                blocksize=chunk_size,
            )
        except Exception as e:
            log.error(
                "Recorder input stream failed to open (device=%s, sample_rate=%s): %s",
                self.config.input_device,
                sample_rate,
                e,
            )
            raise

        with stream_ctx as stream:
            for _ in range(max_chunks):
                chunk, _ = stream.read(chunk_size)
                chunk_flat = chunk.flatten()
                rms = float(np.sqrt(np.mean(chunk_flat ** 2)))

                frames.append(chunk_flat)

                if rms > silence_thresh:
                    has_speech = True
                    silent_chunks = 0
                elif has_speech:
                    silent_chunks += 1
                    if silent_chunks >= silent_chunks_needed:
                        log.debug("Silence detected after %d chunks of speech", len(frames))
                        break

        if not has_speech:
            return None

        return np.concatenate(frames)

    async def transcribe(self, audio_path: Path) -> str:
        """Transcribe audio file to text using faster-whisper."""
        self._load_whisper()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._transcribe_blocking, audio_path)

    def _transcribe_blocking(self, audio_path: Path) -> str:
        try:
            segments, info = self._whisper.transcribe(
                str(audio_path),
                beam_size=5,
                language="en",
                condition_on_previous_text=False,
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()
            log.debug("Transcribed (%.2fs audio): %r", info.duration, text)
            return text
        except Exception as e:
            log.error("Transcription error: %s", e)
            return ""
        finally:
            try:
                audio_path.unlink()
            except Exception:
                pass
