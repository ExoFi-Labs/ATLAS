class NoOpSTT:
    async def transcribe(self, audio_bytes: bytes, *, mime_type: str = "audio/wav") -> str:
        raise RuntimeError("STT is disabled (ATLAS_STT__PROVIDER=none)")
