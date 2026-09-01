"""Voice-ready interface. Swap STT/TTS providers without changing the agent."""

from abc import ABC, abstractmethod


class SpeechToText(ABC):
    @abstractmethod
    async def transcribe(self, audio: bytes, mime_type: str) -> str:
        raise NotImplementedError


class TextToSpeech(ABC):
    @abstractmethod
    async def speak(self, text: str, language: str) -> bytes:
        raise NotImplementedError


class NullSpeechProvider(SpeechToText, TextToSpeech):
    async def transcribe(self, audio: bytes, mime_type: str) -> str:
        raise NotImplementedError("Configure a speech-to-text provider to enable voice.")

    async def speak(self, text: str, language: str) -> bytes:
        raise NotImplementedError("Configure a text-to-speech provider to enable voice.")
