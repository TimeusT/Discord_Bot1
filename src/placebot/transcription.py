"""Turns a video's audio into text, running locally so there is no extra cost or account."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

log = logging.getLogger(__name__)


class Transcriber:
    def __init__(self, model_size: str) -> None:
        self._model_size = model_size
        self._model = None
        self._lock = threading.Lock()  # the speech model handles one video at a time

    def transcribe(self, audio_path: Path) -> str:
        """Return the spoken words in any language (the language is detected automatically)."""
        with self._lock:
            if self._model is None:
                # Imported here so the bot starts fast and the model downloads on first use.
                from faster_whisper import WhisperModel

                log.info("Loading speech model '%s' (first use may download it)", self._model_size)
                self._model = WhisperModel(self._model_size, device="cpu", compute_type="int8")

            segments, _info = self._model.transcribe(str(audio_path), vad_filter=True)
            return " ".join(segment.text.strip() for segment in segments)
