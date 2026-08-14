from __future__ import annotations

import os

from google.cloud import texttospeech

from atlas.config import TTSSettings


class GoogleTTS:
    def __init__(self, settings: TTSSettings) -> None:
        self.settings = settings
        if settings.google_credentials_file:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_credentials_file
        self._client = texttospeech.TextToSpeechClient()

    async def synthesize(self, text: str) -> bytes:
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=self.settings.google_language,
            name=self.settings.google_voice,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.05,
        )

        # google client is sync; offload to thread in API layer if needed
        response = self._client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )
        return response.audio_content
