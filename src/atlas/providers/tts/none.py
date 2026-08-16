class NoOpTTS:
    async def synthesize(
        self,
        text: str,
        *,
        speaking_rate: float | None = None,
        voice: str | None = None,
    ) -> bytes:
        raise RuntimeError("TTS is disabled (ATLAS_TTS__PROVIDER=none)")
