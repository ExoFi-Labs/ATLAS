import io
import wave

import numpy as np

from atlas.config import STTSettings
from atlas.providers.stt.whisper import (
    WhisperSTT,
    audio_suffix,
    is_wav,
    resample_mono,
    wav_to_float32,
)
from atlas.providers.tts.google import language_for_voice


def _wav_bytes(samples: np.ndarray, rate: int = 16000) -> bytes:
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm)
    return buf.getvalue()


def test_audio_suffix_keeps_webm():
    assert audio_suffix("audio/webm;codecs=opus") == ".webm"
    assert audio_suffix("audio/wav") == ".wav"


def test_silero_vad_skips_short_clips():
    on = WhisperSTT.__new__(WhisperSTT)
    on.settings = STTSettings(vad=True, vad_threshold=0.4, vad_min_silence_ms=700)
    options = on._vad_options(16000 * 3)
    assert options["vad_filter"] is True
    assert options["vad_parameters"]["threshold"] == 0.4
    assert on._vad_options(800) == {"vad_filter": False}
    off = WhisperSTT.__new__(WhisperSTT)
    off.settings = STTSettings(vad=False)
    assert off._vad_options(48000) == {"vad_filter": False}


def test_wav_roundtrip_and_resample():
    tone = np.sin(np.linspace(0, 8 * np.pi, 8000)).astype(np.float32)
    data = _wav_bytes(tone, 8000)
    assert is_wav(data)
    audio, rate = wav_to_float32(data)
    assert rate == 8000
    assert audio.shape[0] == 8000
    stretched = resample_mono(audio, 8000, 16000)
    assert stretched.shape[0] == 16000


def test_language_from_google_voice_name():
    assert language_for_voice("en-AU-Chirp3-HD-Kore") == "en-AU"
    assert language_for_voice("en-US-Studio-O") == "en-US"
