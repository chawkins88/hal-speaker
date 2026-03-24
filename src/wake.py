"""
Wake word detection using openWakeWord.

openWakeWord supports custom models and ships with 'hey_jarvis', 'alexa', etc.
For 'hey_hal' you'd train or use a community model.
Falls back to 'hey_jarvis' as placeholder until a custom model is trained.

See: https://github.com/dscripka/openWakeWord
"""

import asyncio
import logging
import numpy as np
from pathlib import Path

from audio_utils import open_input_stream_with_fallback

log = logging.getLogger("wake")

CHUNK_SAMPLES = 1280  # ~80ms at 16kHz (openWakeWord expects this chunk size)


class WakeWordDetector:
    def __init__(self, config):
        self.config = config
        self._oww = None
        self._model_name = config.wake_word
        self._threshold = config.wake_word_threshold
        self._loop = None

    def _load_model(self):
        """Lazy-load openWakeWord model."""
        if self._oww is not None:
            return

        try:
            from openwakeword.model import Model
            # Try to load custom model first, fall back to built-in
            model_path = Path(__file__).parent.parent / "models" / f"{self._model_name}.onnx"
            if model_path.exists():
                log.info("Loading custom wake word model: %s", model_path)
                self._oww = Model(wakeword_models=[str(model_path)])
            else:
                log.warning(
                    "Custom model %s not found, using 'hey_jarvis' as placeholder. "
                    "Train a custom 'hey_hal' model for production.",
                    self._model_name,
                )
                self._oww = Model(wakeword_models=["hey_jarvis"])
        except ImportError:
            raise RuntimeError(
                "openWakeWord not installed. Run: pip install openwakeword"
            )

    async def wait_for_wake_word(self) -> bool:
        """
        Stream audio from mic and return True when wake word is detected.
        This runs in a thread executor to avoid blocking the event loop.
        """
        self._load_model()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._detect_blocking)

    def _detect_blocking(self) -> bool:
        """Blocking wake word detection. Runs in thread."""
        detected = False
        try:
            stream_ctx = open_input_stream_with_fallback(
                samplerate=self.config.sample_rate,
                channels=1,
                dtype="int16",
                device=self.config.input_device,
                blocksize=CHUNK_SAMPLES,
            )
        except Exception as e:
            log.error(
                "Wake-word input stream failed to open (device=%s, sample_rate=%s): %s",
                self.config.input_device,
                self.config.sample_rate,
                e,
            )
            raise

        with stream_ctx as stream:
            while not detected:
                audio_chunk, _ = stream.read(CHUNK_SAMPLES)
                audio_np = audio_chunk.flatten().astype(np.float32) / 32768.0

                predictions = self._oww.predict(audio_np)
                for model_name, score in predictions.items():
                    if score >= self._threshold:
                        log.debug("Wake word '%s' score=%.3f", model_name, score)
                        detected = True
                        break

        return detected
