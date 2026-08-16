from __future__ import annotations

import asyncio
import io
import wave

import numpy as np
from faster_whisper import WhisperModel

from atlas.config import STTSettings

TARGET_RATE = 16000


def audio_suffix(mime_type: str) -> str:
    base = (mime_type or "").split(";", 1)[0].strip().lower()
    return {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/wave": ".wav",
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
    }.get(base, ".wav")


def is_wav(data: bytes) -> bool:
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"


def wav_to_float32(data: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(data), "rb") as handle:
        channels = handle.getnchannels()
        sample_rate = handle.getframerate()
        width = handle.getsampwidth()
        frames = handle.readframes(handle.getnframes())
    if width == 2:
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif width == 4:
        audio = np.frombuffer(frames, dtype=np.float32)
    else:
        raise RuntimeError(f"Unsupported WAV sample width: {width}")
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1).astype(np.float32)
    return np.ascontiguousarray(audio.reshape(-1), dtype=np.float32), int(sample_rate)


def resample_mono(audio: np.ndarray, sample_rate: int, target: int = TARGET_RATE) -> np.ndarray:
    audio = np.ascontiguousarray(np.asarray(audio, dtype=np.float32).reshape(-1))
    if sample_rate == target or audio.size == 0:
        return audio
    length = int(round(audio.size * target / sample_rate))
    if length <= 1:
        return audio
    old_x = np.linspace(0.0, 1.0, audio.size, endpoint=False)
    new_x = np.linspace(0.0, 1.0, length, endpoint=False)
    return np.ascontiguousarray(np.interp(new_x, old_x, audio).astype(np.float32))


class WhisperSTT:
    def __init__(self, settings: STTSettings) -> None:
        self.settings = settings
        self._model: WhisperModel | None = None

    def _ensure_model(self) -> WhisperModel:
        if self._model is None:
            device = self.settings.whisper_device or "cpu"
            compute = "int8" if device == "cpu" else "default"
            self._model = WhisperModel(
                self.settings.whisper_model,
                device=device,
                compute_type=compute,
            )
        return self._model

    def _vad_options(self, samples: int) -> dict:
        # NumPy + Silero VAD raises "chunk is too short" on brief mic clips.
        if (not self.settings.vad) or samples < TARGET_RATE * 2:
            return {"vad_filter": False}
        return {
            "vad_filter": True,
            "vad_parameters": {
                "threshold": float(self.settings.vad_threshold),
                "min_silence_duration_ms": int(self.settings.vad_min_silence_ms),
                "speech_pad_ms": 200,
            },
        }

    def _pcm(self, audio_bytes: bytes, mime_type: str) -> np.ndarray:
        if is_wav(audio_bytes):
            audio, rate = wav_to_float32(audio_bytes)
            return resample_mono(audio, rate)
        raise RuntimeError(
            f"Expected WAV from the chat page, got {mime_type or 'unknown'} ({len(audio_bytes)} bytes)."
        )

    async def transcribe(self, audio_bytes: bytes, *, mime_type: str = "audio/wav") -> str:
        pcm = self._pcm(audio_bytes, mime_type)
        if pcm.size < int(TARGET_RATE * 0.4):
            return ""
        model = self._ensure_model()
        options = self._vad_options(pcm.size)

        def _run() -> str:
            segments, _info = model.transcribe(
                pcm,
                language="en",
                beam_size=1,
                condition_on_previous_text=False,
                **options,
            )
            return " ".join(segment.text.strip() for segment in segments if segment.text).strip()

        return await asyncio.to_thread(_run)
