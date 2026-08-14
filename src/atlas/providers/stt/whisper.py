from __future__ import annotations

import asyncio
import tempfile

from faster_whisper import WhisperModel

from atlas.config import STTSettings


class WhisperSTT:
    def __init__(self, settings: STTSettings) -> None:
        self.settings = settings
        self._model = WhisperModel(settings.whisper_model, device=settings.whisper_device)

    async def transcribe(self, audio_bytes: bytes, *, mime_type: str = "audio/wav") -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as handle:
            handle.write(audio_bytes)
            handle.flush()
            segments, _ = await asyncio.to_thread(
                self._model.transcribe,
                handle.name,
                beam_size=5,
                vad_filter=True,
            )
        return " ".join(segment.text.strip() for segment in segments).strip()
