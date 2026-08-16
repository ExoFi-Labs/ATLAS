from __future__ import annotations

import asyncio
import os
import re

from google.cloud import texttospeech

from atlas.config import TTSSettings

_LANG = re.compile(r"^([a-z]{2}-[A-Z]{2})")


def language_for_voice(voice_name: str, fallback: str = "en-AU") -> str:
    match = _LANG.match(voice_name or "")
    return match.group(1) if match else fallback


class GoogleTTS:
    def __init__(self, settings: TTSSettings) -> None:
        self.settings = settings
        if settings.google_credentials_file:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_credentials_file
        self._client = texttospeech.TextToSpeechClient()

    async def synthesize(
        self,
        text: str,
        *,
        speaking_rate: float | None = None,
        voice: str | None = None,
    ) -> bytes:
        clipped = (text or "").strip()
        if len(clipped) > 4500:
            clipped = clipped[:4500]
        rate = float(speaking_rate if speaking_rate is not None else self.settings.speaking_rate or 1.0)
        rate = min(2.0, max(0.5, rate))
        voice_name = (voice or self.settings.google_voice or "en-AU-Chirp3-HD-Kore").strip()
        language = language_for_voice(voice_name, self.settings.google_language or "en-AU")
        synthesis_input = texttospeech.SynthesisInput(text=clipped)
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=language,
            name=voice_name,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=rate,
        )
        response = await asyncio.to_thread(
            self._client.synthesize_speech,
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
        )
        return response.audio_content
