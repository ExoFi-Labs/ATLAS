class NoOpTTS:
    async def synthesize(self, text: str) -> bytes:
        raise RuntimeError("TTS is disabled (ATLAS_TTS__PROVIDER=none)")
