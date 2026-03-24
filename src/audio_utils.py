import logging
from typing import Any

import sounddevice as sd

log = logging.getLogger("audio")


def open_input_stream_with_fallback(*, samplerate: int, channels: int, dtype: str, device: int | None, blocksize: int):
    """
    Try the requested input device first. If it fails and a specific device was requested,
    retry once with the system default input device.
    """
    try:
        return sd.InputStream(
            samplerate=samplerate,
            channels=channels,
            dtype=dtype,
            device=device,
            blocksize=blocksize,
        )
    except Exception as e:
        if device is None:
            raise
        log.warning(
            "Failed to open input device %s at %s Hz (%s). Falling back to system default input device.",
            device,
            samplerate,
            e,
        )
        return sd.InputStream(
            samplerate=samplerate,
            channels=channels,
            dtype=dtype,
            device=None,
            blocksize=blocksize,
        )
